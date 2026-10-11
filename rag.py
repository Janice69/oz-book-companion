"""Local RAG: JSON passages -> embeddings -> retrieval -> generated answer."""
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForQuestionAnswering, AutoModelForSeq2SeqLM, AutoTokenizer

ROOT = Path(__file__).parent
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
ANSWER_MODEL = os.getenv("RAG_ANSWER_MODEL", "google/flan-t5-base")
NO_ANSWER = "I couldn't find enough evidence in the book to answer that question. Try asking about a character, place, or event in The Wonderful Wizard of Oz."
STOP_WORDS = set("a an the is are was were be been to of in on at for from and or with what who where when why how does do did can could would should tell me about please it its his her their they he she i you my this that which book".split())


def search_terms(text):
    # Group simple word variants, such as live/lived and want/wants.
    return [re.sub(r"e$", "", re.sub(r"(?:ing|ed|es|s)$", "", word))
            for word in re.findall(r"[a-z]+", text.lower()) if word not in STOP_WORDS]


def lexical_scores(question, texts):
    """BM25 word matching complements meaning-based similarity."""
    from collections import Counter
    documents = [Counter(search_terms(text)) for text in texts]
    lengths = np.array([sum(doc.values()) for doc in documents])
    average = max(1, float(lengths.mean()))
    scores = np.zeros(len(texts))
    for term in set(search_terms(question)):
        frequencies = np.array([doc[term] for doc in documents])
        count = int((frequencies > 0).sum())
        inverse_frequency = np.log(1 + (len(texts) - count + 0.5) / (count + 0.5))
        scores += inverse_frequency * frequencies * 2.5 / (frequencies + 1.5 * (0.25 + 0.75 * lengths / average))
    return scores / max(1, float(scores.max()))


def load_cached(loader, name, **kwargs):
    """Use already-downloaded models without waiting for network checks."""
    try:
        return loader(name, local_files_only=True, **kwargs)
    except OSError:
        return loader(name, **kwargs)


class BookRAG:
    def __init__(self):
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        path = ROOT / "passages.json"
        if not path.exists():
            raise RuntimeError("Run python split_passages.py first.")
        self.passages = json.loads(path.read_text(encoding="utf-8"))
        self.encoder = load_cached(SentenceTransformer, EMBED_MODEL, device="cpu")
        cache = ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        digest = hashlib.sha256(path.read_bytes() + EMBED_MODEL.encode()).hexdigest()[:16]
        passage_path = cache / f"passages-{digest}.npy"
        if passage_path.exists():
            self.passage_vectors = np.load(passage_path, allow_pickle=False)
        else:
            self.passage_vectors = self.encoder.encode(
                [passage["text"] for passage in self.passages],
                normalize_embeddings=True, show_progress_bar=True,
                convert_to_numpy=True,
            )
            np.save(passage_path, self.passage_vectors)
        self.tokenizer = load_cached(AutoTokenizer.from_pretrained, ANSWER_MODEL)
        self.model = load_cached(AutoModelForSeq2SeqLM.from_pretrained, ANSWER_MODEL).eval()
        reader_name = "deepset/minilm-uncased-squad2"
        self.reader_tokenizer = load_cached(AutoTokenizer.from_pretrained, reader_name)
        self.reader = load_cached(AutoModelForQuestionAnswering.from_pretrained, reader_name).eval()

    def retrieve(self, question, limit=120):
        query = self.encoder.encode(question, normalize_embeddings=True)
        semantic = self.passage_vectors @ query
        lexical = lexical_scores(question, [passage["text"] for passage in self.passages])
        scores = 0.5 * semantic + 0.5 * lexical
        order = np.argsort(-scores)
        results = []
        # Suppress neighboring overlaps with nearly identical text.
        for index in order:
            passage = self.passages[int(index)]
            words = set(passage["text"].lower().split())
            if any(len(words & existing) / max(1, len(words | existing)) > 0.65
                   for existing in [set(p["text"].lower().split()) for p in results]):
                continue
            results.append({**passage, "score": round(float(scores[index]), 4)})
            if len(results) == limit:
                break
        return results

    def answer(self, question):
        sources = self.retrieve(question)
        terms = set(search_terms(question))
        evidence_terms = set(search_terms(" ".join(p["text"] for p in sources)))
        if not sources or sources[0]["score"] < 0.30 or not (terms & evidence_terms):
            return {"answer": NO_ANSWER, "sources": [], "answered": False}
        match = self.read_evidence(question, sources)
        if match is None or match["margin"] < 1.0:
            return {"answer": NO_ANSWER, "sources": [], "answered": False}
        source = match["source"]
        # Keep the supported span explicitly in the generation context.
        context = f"Supported answer: {match['text']}. Passage: {source['text']}"
        prompt = self.make_prompt(question, context)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=100, num_beams=4, do_sample=False)
        answer = self.tokenizer.decode(output[0], skip_special_tokens=True).strip()
        if not answer or answer.lower().rstrip(".") in {"unknown", "i don't know", "not enough information", "unanswerable"}:
            return {"answer": NO_ANSWER, "sources": [], "answered": False}
        # If generation omits the selected evidence entirely, return the exact span.
        if not (set(search_terms(answer)) & set(search_terms(match["text"]))):
            answer = match["text"]
        return {"answer": answer, "sources": [source], "answered": True}

    def read_evidence(self, question, sources):
        """Find an answer span and compare it against the reader's no-answer score."""
        best = None
        short_question = " ".join(question.split()[:64])
        for start in range(0, len(sources), 12):
            batch = sources[start:start + 12]
            encoded = self.reader_tokenizer(
                [short_question] * len(batch), [s["text"] for s in batch],
                truncation="only_second", max_length=384, padding=True,
                return_offsets_mapping=True, return_tensors="pt",
                return_overflowing_tokens=True, stride=64,
            )
            offsets = encoded.pop("offset_mapping")
            mapping = encoded.pop("overflow_to_sample_mapping")
            with torch.inference_mode():
                result = self.reader(**encoded)
            for row in range(len(mapping)):
                source = batch[int(mapping[row])]
                sequence = encoded.sequence_ids(row)
                valid = np.array([kind == 1 and int(offsets[row, i, 1]) > int(offsets[row, i, 0])
                                  for i, kind in enumerate(sequence)])
                beginnings = result.start_logits[row].numpy().copy()
                endings = result.end_logits[row].numpy().copy()
                null_score = float(beginnings[0] + endings[0])
                beginnings[~valid] = -1e9
                endings[~valid] = -1e9
                for left in np.argsort(-beginnings)[:10]:
                    for right in range(int(left), min(int(left) + 30, len(endings))):
                        if not valid[right]:
                            continue
                        margin = float(beginnings[left] + endings[right]) - null_score
                        if best is None or margin > best["margin"]:
                            lo, hi = int(offsets[row, left, 0]), int(offsets[row, right, 1])
                            best = {"margin": margin, "text": source["text"][lo:hi], "source": source}
        return best

    @staticmethod
    def make_prompt(question, context):
        return ("Answer the question using only the context. If the answer is not in the context, "
                f"say unknown.\nContext: {context}\nQuestion: {question}\nAnswer:")


if __name__ == "__main__":
    chatbot = BookRAG()
    print("\nBook chatbot ready. Type quit to stop.")
    while True:
        question = input("\nYou: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            continue
        result = chatbot.answer(question)
        print("\nBook companion:", result["answer"])
        for source in result["sources"]:
            print(f"  Source: {source['chapter']} — {source['title']} ({source['id']})")
