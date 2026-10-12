"""Assemble ordinary content, warnings, and tables into retrieval chunks."""

import re
from pathlib import Path

import pymupdf

from noesis.ingest.chunking import (
    DEFAULT_CHILD_SIZE,
    DEFAULT_OVERLAP,
    DEFAULT_PARENT_SIZE,
    Chunk,
    approx_tokens,
    chunk_lines,
)
from noesis.ingest.chunking import Chunk, chunk_lines
from noesis.ingest.pdf import extract_pdf
from noesis.ingest.sections import SectionLine, detect_sections
from noesis.ingest.tables import extract_tables
from noesis.ingest.warnings import extract_warnings


def _overlaps(a: tuple, b: tuple) -> bool:
    """Return whether two PDF bounding boxes overlap."""
    return (
        a[0] < b[2]
        and a[2] > b[0]
        and a[1] < b[3]
        and a[3] > b[1]
    )




def _table_section(
    table: dict,
    lines: list[SectionLine],
) -> str:
    """Find the nearest preceding section for a table.

    Prefer section context on the same page. If none exists,
    use the latest section established on an earlier page.
    """
    preceding = [
        line
        for line in lines
        if line["section_path"]
        and (
            line["page"] < table["page"]
            or (
                line["page"] == table["page"]
                and line["bbox"][1] <= table["bbox"][1]
            )
        )
    ]

    if not preceding:
        return ""

    nearest = max(
        preceding,
        key=lambda line: (
            line["page"],
            line["bbox"][1],
        ),
    )
    return nearest["section_path"]


def assemble_document(
    pdf_path: str | Path,
    *,
    parent_size: int = DEFAULT_PARENT_SIZE,
    child_size: int = DEFAULT_CHILD_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    source_class: str = "APPROVED_DOC",
) -> list[Chunk]:
    """Extract and assemble a PDF into content, warning, and table chunks.

    This function does not write to SQLite. Database IDs are assigned later
    by the persistence layer.
    """
    raw_lines = extract_pdf(pdf_path)
    tables = extract_tables(pdf_path)

# Remove standalone page numbers in the bottom 15% of each page.
# Filter before section detection so numbers cannot become headings,
# parent chunks, or ordinary content chunks.
    with pymupdf.open(pdf_path) as document:
         page_heights = {
            page_number: float(page.rect.height)
            for page_number, page in enumerate(document, start=1)
    }

    raw_lines = [
        line
        for line in raw_lines
        if not (
           re.fullmatch(r"\d{1,4}", line["text"].strip())
           and line["page"] in page_heights
           and line["bbox"][1] >= 0.85 * page_heights[line["page"]]
    )
]
    
    table_regions = [
        (table["page"], table["bbox"])
        for table in tables
    ]
    
    lines = detect_sections(
        pdf_path,
        raw_lines,
        excluded_regions=table_regions,
    )
    warnings = extract_warnings(lines)
    

    # Exclude warning labels and their captured text from ordinary content.
    warning_spans = [
        (warning["page_start"], warning["char_start"], warning["char_end"])
        for warning in warnings
    ]

    # Exclude table cells and captions from ordinary content.
    table_captions = {
        (table["page"], table["caption"])
        for table in tables
        if table["caption"]
    }

    ordinary_lines: list[SectionLine] = []

    for line in lines:
        if not line["section_path"].strip():
            continue

        if any(
            line["page"] == page
            and line["char_start"] >= start
            and line["char_end"] <= end
            for page, start, end in warning_spans
        ):
            continue

        if (line["page"], line["text"].strip()) in table_captions:
            continue

        if any(
            line["page"] == table["page"]
            and _overlaps(line["bbox"], table["bbox"])
            for table in tables
        ):
            continue

        ordinary_lines.append(line)

    chunks = chunk_lines(
        ordinary_lines,
        parent_size=parent_size,
        child_size=child_size,
        overlap=overlap,
        source_class=source_class,
    )

    # Add each warning as a standalone typed chunk.
    for index, warning in enumerate(warnings, start=1):
        section = warning["section_path"]
        text = f'{warning["label"]}: {warning["text"]}'

        chunks.append(
               {
                "chunk_key": f"warning-{index}",
                "parent_chunk_key": None,
                "page_start": warning["page_start"],
                "page_end": warning["page_end"],
                "section_path": section,
                "heading_level": None,
                "chunk_role": "warning",
                "table_id": None,
                "text": text,
                "text_for_embedding": f"Section: {section}\n{text}",
                "char_start": warning["char_start"],
                "char_end": warning["char_end"],
                "token_count": approx_tokens(text),
                "safety_scope": warning["safety_scope"],
                "source_class": source_class,
            }
        )

    # Add each table as a standalone structured retrieval unit.
    for index, table in enumerate(tables, start=1):
        section = _table_section(table, lines)

        table_lines = [
            " | ".join(table["headers"]),
            *(" | ".join(row) for row in table["rows"]),
        ]

        table_text = "\n".join(table_lines)
        if table["caption"]:
            table_text = f'{table["caption"]}\n{table_text}'

        chunks.append(
            {
                "chunk_key": f"table-{index}",
                "parent_chunk_key": None,
                "page_start": table["page"],
                "page_end": table["page"],
                "section_path": section,
                "heading_level": None,
                "chunk_role": "table",
                "table_id": table["table_id"],
                "text": table_text,
                "text_for_embedding": (
                    f"Section: {section}\n{table_text}"
                ),
                "char_start": None,
                "char_end": None,
                "token_count": approx_tokens(table_text),
                "safety_scope": None,
                "source_class": source_class,
            }
        )

    return chunks
