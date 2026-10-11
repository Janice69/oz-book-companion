"""Run real retrieval and answer checks; first run downloads the models."""
from rag import BookRAG


def main():
    bot = BookRAG()
    prompts = []
    original_prompt = bot.make_prompt
    def capture_prompt(question, context):
        prompt = original_prompt(question, context)
        prompts.append(prompt)
        return prompt
    bot.make_prompt = capture_prompt
    cases = [
        ("Where does Dorothy live?", "kansas"),
        ("What does the Scarecrow ask Oz to give him?", "brain"),
        ("What does the Tin Woodman ask the Wizard to give him?", "heart"),
        ("How does Dorothy defeat the Wicked Witch?", "water"),
    ]
    for question, expected in cases:
        result = bot.answer(question)
        print(f"\nQ: {question}\nA: {result['answer']}", flush=True)
        print("Sources:", [s["chapter"] for s in result["sources"]], flush=True)
        if expected not in result["answer"].lower():
            print("Evidence prompt:", prompts[-1], flush=True)
        assert result["answered"] and expected in result["answer"].lower(), question
        assert result["sources"] and all(s["id"] and s["text"] for s in result["sources"])
    unrelated = bot.answer("How do I install a PostgreSQL database on Ubuntu Linux?")
    assert not unrelated["answered"] and not unrelated["sources"]
    print("\nPASS: four factual answers with sources; unrelated question declined.", flush=True)


if __name__ == "__main__":
    main()
