from pathlib import Path


# Look for the book in the same folder as this script.
book_path = Path(__file__).parent / "Wizard of Oz.txt"

# Read the file into one Python string.
book_text = book_path.read_text(encoding="utf-8")

print(f"Loaded {book_path.name}")
print(f"Characters: {len(book_text):,}")
print("\nPreview (first 300 characters):")
print(book_text[:300])
