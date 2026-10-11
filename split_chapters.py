import re
from pathlib import Path


def split_chapters(book_text):
    """Return chapter labels, titles, and text from this book."""
    # Remove the license material after the story.
    story = book_text.split("*** END OF THE PROJECT GUTENBERG EBOOK", 1)[0]

    # Match chapter headings on their own lines, not contents-list entries.
    headings = list(re.finditer(r"^Chapter [IVXLCDM]+\n([^\n]+)", story, re.MULTILINE))
    chapters = []

    for index, heading in enumerate(headings):
        next_start = headings[index + 1].start() if index + 1 < len(headings) else len(story)
        chapters.append({
            "chapter": heading.group(0).split("\n")[0],
            "title": heading.group(1).strip(),
            "text": story[heading.end():next_start].strip(),
        })

    return chapters


if __name__ == "__main__":
    book_path = Path(__file__).parent / "Wizard of Oz.txt"
    chapters = split_chapters(book_path.read_text(encoding="utf-8"))
    print(f"Found {len(chapters)} chapters\n")
    for chapter in chapters:
        print(f"{chapter['chapter']}: {chapter['title']} ({len(chapter['text']):,} characters)")
