
import pymupdf
from pathlib import Path

pdf_path = Path("corpus/osha_lockout_tagout.pdf")

if not pdf_path.exists():
    raise FileNotFoundError(f"PDF not found: {pdf_path}")

terms = (
     "control of hazardous energy",
    "lockout",
    "tagout",
    "energy-isolating device",
    "authorized employee",
    "maintenance",
)

total_chars = 0

with pymupdf.open(pdf_path) as doc:
    print(f"Pages: {len(doc)}")

    for i, page in enumerate(doc):
        text = page.get_text()
        total_chars += len(text.strip())

        matched = [
            term for term in terms
            if term in text.lower()
        ]

        if matched:
            print(f"\nPage {i + 1}: {', '.join(matched)}")
            print(text[:1000])

    print(f"\nExtracted characters: {total_chars}")
# import pymupdf
# from pathlib import Path

# pdf_path = Path("corpus/lubrication_sop.pdf")

# with pymupdf.open(pdf_path) as doc:
#     print("Pages:", len(doc))

#     for i, page in enumerate(doc):
#         text = page.get_text()
#         images = page.get_images()

#         print(
#             f"Page {i + 1}: "
#             f"text_chars={len(text.strip())}, "
#             f"images={len(images)}"
#         )