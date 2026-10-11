
"""Extract line-level text and layout metadata from PDFs."""

from pathlib import Path
from typing import TypedDict

import pymupdf


class ExtractedLine(TypedDict):
    page: int
    text: str
    size: float
    bold: bool
    bbox: tuple[float, float, float, float]
    char_start: int
    char_end: int


def extract_pdf(pdf_path: str | Path) -> list[ExtractedLine]:
    """Extract text lines with offsets into each page's plain text.

    Offsets are zero-based and end-exclusive. They refer to the exact
    string returned by page.get_text("text"), not document-wide text.
    """
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    extracted: list[ExtractedLine] = []

    with pymupdf.open(path) as document:
        if document.is_encrypted:
            raise ValueError(f"Encrypted PDFs are unsupported: {path}")

        for page_index, page in enumerate(document, start=1):
            page_text = page.get_text("text")
            layout = page.get_text("dict")
            cursor = 0

            for block in layout["blocks"]:
                if "lines" not in block:
                    continue

                for line in block["lines"]:
                    spans = [
                        span for span in line["spans"]
                        if span["text"]
                    ]

                    if not spans:
                        continue

                    text = "".join(span["text"] for span in spans)
                    if not text.strip():
                        continue

                    # Match against the same page-text representation
                    # that the evidence endpoint will later serve.
                    start = page_text.find(text, cursor)

                    if start < 0:
                        # Layout extraction can differ slightly from
                        # plain-text extraction. Try from the beginning
                        # before declaring the offset unavailable.
                        start = page_text.find(text)

                    if start < 0:
                        raise ValueError(
                            "Could not map extracted line to page text "
                            f"(page={page_index}, text={text!r})"
                        )

                    end = start + len(text)
                    cursor = end

                    x0, y0, x1, y1 = line["bbox"]
                    extracted.append(
                        {
                            "page": page_index,
                            "text": text,
                            "size": max(
                                float(span["size"]) for span in spans
                            ),
                            "bold": any(
                                "bold" in span["font"].lower()
                                or bool(span["flags"] & 16)
                                for span in spans
                            ),
                            "bbox": (
                                float(x0),
                                float(y0),
                                float(x1),
                                float(y1),
                            ),
                            "char_start": start,
                            "char_end": end,
                        }
                    )

    return extracted
