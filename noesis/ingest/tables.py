
"""Extract structured tables from PDFs using PyMuPDF."""

import re
from pathlib import Path
from typing import TypedDict

import pymupdf


class ExtractedTable(TypedDict):
    table_id: str
    page: int
    bbox: tuple[float, float, float, float]
    caption: str | None
    headers: list[str]
    rows: list[list[str]]


CAPTION_PATTERN = re.compile(
    r"^\s*Table\s+[\w.-]+\s*[·:.-]?\s*(.*?)\s*$",
    re.IGNORECASE,
)


def _find_caption(page, table_bbox) -> str | None:
    """Find the nearest preceding table caption on the same page."""
    candidates = []

    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue

        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            match = CAPTION_PATTERN.match(text)

            if not match:
                continue

            y_bottom = float(line["bbox"][3])
            table_top = float(table_bbox[1])

            # A caption should be above the table and reasonably close.
            if 0 <= table_top - y_bottom <= 60:
                candidates.append((table_top - y_bottom, text))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def extract_tables(pdf_path: str | Path) -> list[ExtractedTable]:
    """Extract tables with page-local provenance and first-row headers."""
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    extracted: list[ExtractedTable] = []

    with pymupdf.open(path) as document:
        if document.is_encrypted:
            raise ValueError(f"Encrypted PDFs are unsupported: {path}")

        for page_number, page in enumerate(document, start=1):
            found = page.find_tables()

            for table_number, table in enumerate(found.tables, start=1):
                raw_rows = table.extract()

                # Normalize cells without changing row/column structure.
                normalized_rows = [
                    [str(cell or "").strip() for cell in row]
                    for row in raw_rows
                ]

                # Ignore empty detections.
                normalized_rows = [
                    row for row in normalized_rows
                    if any(cell for cell in row)
                ]

                if not normalized_rows:
                    continue

                bbox = tuple(float(value) for value in table.bbox)

                extracted.append(
                    {
                        "table_id": f"p{page_number}-t{table_number}",
                        "page": page_number,
                        "bbox": bbox,
                        "caption": _find_caption(page, bbox),
                        "headers": normalized_rows[0],
                        "rows": normalized_rows[1:],
                    }
                )

    return extracted
