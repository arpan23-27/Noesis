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


# Corpus-tuned heuristics from the Phase 1 audit. Re-run the audit if the
# corpus changes.
PROSE_MIN_AVG_CHARS = 150   # long average cell ...
PROSE_MAX_ROWS = 2          # ... in a table this short is page prose
WARNING_BOX_MAX_COLS = 4    # warning boxes are drawn as 3-column tables
FORWARD_FILL_MAX_COLS = 4   # blank symptom cells repeat down narrow tables
MAX_HEADER_CELL_CHARS = 80

SIGNAL_WORD = re.compile(r"^(WARNING|CAUTION|DANGER|NOTICE)\b")
CAPTION_PATTERN = re.compile(
    r"^\s*Table\s+[\w.-]+\s*[\u00b7:.\u2013-]?\s*(.*?)\s*$",
    re.IGNORECASE,
)
BULLET_GLYPHS = "\u2022\u25aa\u25cf-*"
SYMBOL_BULLETS = {"\uf0b7": "\u2022", "\uf0a7": "\u2022"}


def clean_cell(value) -> str:
    """Normalize one cell: Symbol-font bullets, whitespace, None."""
    text = str(value or "")
    for glyph, replacement in SYMBOL_BULLETS.items():
        text = text.replace(glyph, replacement)
    return re.sub(r"\s+", " ", text).strip()


def looks_like_header(cells: list[str]) -> bool:
    """False for rows that are clearly body text, e.g. a continued table."""
    filled = [cell for cell in cells if cell]
    if not filled:
        return False
    return all(
        len(cell) <= MAX_HEADER_CELL_CHARS
        and cell[0] not in BULLET_GLYPHS
        and not cell[0].islower()
        for cell in filled
    )


def rejection_reason(matrix: list[list[str]], min_rows: int = 2) -> str | None:
    """Return why a detection is not a real table, or None to keep it."""
    if len(matrix) < min_rows:
        return "too_few_rows"

    cells = [cell for row in matrix for cell in row if cell]
    if not cells:
        return "empty"

    average = sum(len(cell) for cell in cells) / len(cells)
    if len(matrix) <= PROSE_MAX_ROWS and average > PROSE_MIN_AVG_CHARS:
        return "page_prose"

    if len(matrix[0]) <= WARNING_BOX_MAX_COLS and any(
        SIGNAL_WORD.match(row[index])
        for row in matrix
        for index in range(min(2, len(row)))
    ):
        return "warning_box"

    return None


def _find_caption(page, table_bbox) -> str | None:
    """Find the nearest preceding table caption on the same page."""
    candidates = []

    for block in page.get_text("dict")["blocks"]:
        if "lines" not in block:
            continue

        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not CAPTION_PATTERN.match(text):
                continue

            gap = float(table_bbox[1]) - float(line["bbox"][3])
            # A caption should be above the table and reasonably close.
            if 0 <= gap <= 60:
                candidates.append((gap, text))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def extract_tables(
    pdf_path: str | Path,
    rejected: list[dict] | None = None,
) -> list[ExtractedTable]:
    """Extract real tables with page-local provenance.

    Detections that are page prose, warning boxes or fragments are dropped;
    pass a list as `rejected` to receive {page, table_id, reason, rows, cols}.
    """
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    extracted: list[ExtractedTable] = []
    last: dict | None = None  # most recent detection, accepted or not

    with pymupdf.open(path) as document:
        if document.is_encrypted:
            raise ValueError(f"Encrypted PDFs are unsupported: {path}")

        for page_number, page in enumerate(document, start=1):
            for table_number, table in enumerate(page.find_tables().tables, start=1):
                matrix = [[clean_cell(cell) for cell in row] for row in table.extract()]
                matrix = [row for row in matrix if any(row)]
                if not matrix:
                    continue

                headers, body = matrix[0], matrix[1:]
                continues = (
                    not looks_like_header(headers)
                    and last is not None
                    and last["page"] == page_number - 1
                    and last["cols"] == len(headers)
                )
                inherit = continues and last["reason"] is None
                if inherit:
                    headers, body = last["headers"], matrix

                reason = rejection_reason(matrix, min_rows=1 if inherit else 2)
                if reason is None and continues and last["reason"] == "warning_box":
                    reason = "warning_box"  # continuation of a warning box

                table_id = f"p{page_number}-t{table_number}"
                last = {
                    "page": page_number,
                    "cols": len(matrix[0]),
                    "headers": headers,
                    "reason": reason,
                }

                if reason:
                    if rejected is not None:
                        rejected.append(
                            {
                                "page": page_number,
                                "table_id": table_id,
                                "reason": reason,
                                "rows": len(matrix),
                                "cols": len(matrix[0]),
                            }
                        )
                    continue

                extracted.append(
                    {
                        "table_id": table_id,
                        "page": page_number,
                        "bbox": tuple(float(value) for value in table.bbox),
                        "caption": _find_caption(page, table.bbox),
                        "headers": headers,
                        "rows": body,
                    }
                )

    return extracted


def table_rows(table: ExtractedTable) -> list[list[str]]:
    """Data rows ready for chunking.

    Drops empty rows and repeated header rows. In narrow tables, a blank
    first cell inherits the value above it (a symptom listed once over
    several cause rows).
    """
    headers = table["headers"]
    width = len(headers)
    fill = width <= FORWARD_FILL_MAX_COLS
    cleaned: list[list[str]] = []
    lead = ""

    for raw in table["rows"]:
        row = (list(raw) + [""] * width)[:width]
        if not any(row) or row == headers:
            continue
        if fill and not row[0] and lead and any(row[1:]):
            row[0] = lead
        if row[0]:
            lead = row[0]
        cleaned.append(row)

    return cleaned


def row_text(table: ExtractedTable, row: list[str]) -> str:
    """Quotable text: caption, header row and one data row."""
    lines = [table["caption"]] if table["caption"] else []
    lines.append(" | ".join(table["headers"]))
    lines.append(" | ".join(row))
    return "\n".join(lines)


def row_sentence(table: ExtractedTable, row: list[str]) -> str:
    """Sentence rendering of one row, for embedding."""
    parts = [
        f"{header or f'Column {index + 1}'}: {value}"
        for index, (header, value) in enumerate(zip(table["headers"], row))
        if value
    ]
    prefix = f"{table['caption']}. " if table["caption"] else ""
    return prefix + "; ".join(parts) + "."