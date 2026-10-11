import json
from pathlib import Path

from split_chapters import split_chapters


def split_passages(chapters, passage_words=180, overlap_words=30):
    """Split chapters into overlapping passages without crossing chapters."""
    if not 0 <= overlap_words < passage_words:
        raise ValueError("Overlap must be nonnegative and smaller than the passage size.")

    passages = []
    step = passage_words - overlap_words

    for chapter in chapters:
        words = chapter["text"].split()
        for start in range(0, len(words), step):
            passages.append({
                "id": f"passage-{len(passages) + 1:04d}",
                "chapter": chapter["chapter"],
                "title": chapter["title"],
                "text": " ".join(words[start:start + passage_words]),
            })
            # Stop once this passage contains the chapter's final word.
            if start + passage_words >= len(words):
                break

    return passages


if __name__ == "__main__":
    book_path = Path(__file__).parent / "Wizard of Oz.txt"
    chapters = split_chapters(book_path.read_text(encoding="utf-8"))
    passages = split_passages(chapters)
    # Save the list as readable JSON for later search code to load.
    output_path = Path(__file__).parent / "passages.json"
    output_path.write_text(
        json.dumps(passages, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Created {len(passages)} passages from {len(chapters)} chapters.")
    print(f"Saved to {output_path.name}")
    first = passages[0]
    print(f"\n{first['id']} | {first['chapter']}: {first['title']}")
    print(f"Words: {len(first['text'].split())}\n")
    print(first["text"])
