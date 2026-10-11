
"""Create section-aware parent and child chunks from extracted PDF lines."""

from typing import TypedDict

from noesis.ingest.sections import SectionLine


class Chunk(TypedDict):
    chunk_key: str
    parent_chunk_key: str | None
    page_start: int
    page_end: int
    section_path: str
    heading_level: int | None
    chunk_role: str
    table_id: str | None
    text: str
    text_for_embedding: str
    char_start: int | None
    char_end: int | None
    token_count: int | None
    safety_scope: str | None
    source_class: str


def _split_text(
    text: str,
    target_size: int,
    overlap: int,
) -> list[tuple[int, int]]:
    """Return non-empty text ranges, preferring word boundaries."""
    if target_size <= 0:
        raise ValueError("target_size must be positive")
    if overlap < 0 or overlap >= target_size:
        raise ValueError("overlap must be >= 0 and < target_size")

    ranges = []
    start = 0

    while start < len(text):
        end = min(start + target_size, len(text))

        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        if end <= start:
            end = min(start + target_size, len(text))

        ranges.append((start, end))

        if end == len(text):
            break

        next_start = max(start + 1, end - overlap)

        # Avoid starting the next chunk in the middle of a word.
        space = text.find(" ", next_start, end)
        if space != -1:
            next_start = space + 1

        start = next_start

    return ranges



def _source_offsets(
    lines: list[SectionLine],
    start: int,
    end: int,
) -> tuple[int | None, int | None]:
    """Return source offsets only when the reconstructed span maps exactly."""
    if not lines or start < 0 or end <= start:
        return None, None

    parts: list[str] = []
    source_positions: list[int | None] = []

    for index, line in enumerate(lines):
        if index:
            previous = lines[index - 1]

            # A reconstructed newline is safe only if the source lines
            # are separated by exactly one newline.
            if line["char_start"] != previous["char_end"] + 1:
                return None, None

            parts.append("\n")
            source_positions.append(None)

        parts.append(line["text"])
        source_positions.extend(
            range(line["char_start"], line["char_end"])
        )

    reconstructed = "".join(parts)

    if len(reconstructed) != len(source_positions):
        return None, None

    if end > len(reconstructed):
        return None, None

    # A source span cannot include a reconstructed separator unless the
    # separator itself maps to the original source.
    selected_positions = source_positions[start:end]

    if not selected_positions or any(
        position is None for position in selected_positions
    ):
        return None, None

    source_start = selected_positions[0]
    source_end = selected_positions[-1] + 1

    # Require a contiguous source range of the same length.
    if source_end - source_start != end - start:
        return None, None

    return source_start, source_end


def chunk_lines(
    lines: list[SectionLine],
    *,
    parent_size: int = 1200,
    child_size: int = 400,
    overlap: int = 60,
    source_class: str = "APPROVED_DOC",
) -> list[Chunk]:
    """Build parent chunks and their child retrieval chunks.

    Chunks never cross page or section boundaries. Parent-child references
    use deterministic in-memory keys; the database integration layer must
    translate these keys into SQLite chunk_id values.

    This first version chunks ordinary text only. Warning and table blocks
    will be integrated as typed units in a later step.
    """
    if parent_size <= 0 or child_size <= 0:
        raise ValueError("Chunk sizes must be positive")
    if overlap < 0 or overlap >= child_size:
        raise ValueError("overlap must be >= 0 and < child_size")

    if source_class not in {"APPROVED_DOC", "RECORD"}:
        raise ValueError("Invalid source_class")

    # Group lines by page and section, preserving input order.
    groups: list[list[SectionLine]] = []

    for line in lines:
        if not line["text"].strip():
            continue

        # Do not create retrieval chunks from lines that have no
        # recognized section context. This currently excludes the
        # synthetic manual's running header and duplicate page title.
        if not line["section_path"].strip():
            continue

        key = (line["page"], line["section_path"])

        if (
            not groups
            or (
                groups[-1][0]["page"],
                groups[-1][0]["section_path"],
            ) != key
        ):
            groups.append([])

        groups[-1].append(line)

    chunks: list[Chunk] = []
    parent_number = 0
    child_number = 0

    for group in groups:
        group_text = "\n".join(line["text"] for line in group)
        page = group[0]["page"]
        section_path = group[0]["section_path"]

        parent_ranges = _split_text(group_text, parent_size, 0)

        for parent_start, parent_end in parent_ranges:
            parent_raw = group_text[parent_start:parent_end]
            parent_left_trim = len(parent_raw) - len(parent_raw.lstrip())
            parent_text = parent_raw.strip()
            if not parent_text:
                continue

            parent_start += parent_left_trim
            parent_end = parent_start + len(parent_text)
            parent_number += 1
            parent_key = f"parent-{parent_number}"

            parent_start_offset, parent_end_offset = _source_offsets(
                group,
                parent_start,
                parent_end,
            )

            heading_levels = [
                line["heading_level"]
                for line in group
                if line["heading_level"] is not None
            ]

            chunks.append(
                {
                    "chunk_key": parent_key,
                    "parent_chunk_key": None,
                    "page_start": page,
                    "page_end": page,
                    "section_path": section_path,
                    "heading_level": (
                        heading_levels[0] if heading_levels else None
                    ),
                    "chunk_role": "parent",
                    "table_id": None,
                    "text": parent_text,
                    "text_for_embedding": (
                        f"Section: {section_path}\n{parent_text}"
                    ),
                    "char_start": parent_start_offset,
                    "char_end": parent_end_offset,
                    "token_count": None,
                    "safety_scope": None,
                    "source_class": source_class,
                }
            )

            # Parent text may be trimmed at its edges. Child offsets are
            # mapped only when the source span can be established safely.
            child_ranges = _split_text(
                parent_text,
                child_size,
                overlap,
            )

            for child_start, child_end in child_ranges:
                child_raw = parent_text[child_start:child_end]
                child_left_trim = len(child_raw) - len(child_raw.lstrip())
                child_text = child_raw.strip()
                
                if not child_text:
                    continue
                
                child_start += child_left_trim
                child_end = child_start + len(child_text)
                child_number += 1
                child_key = f"child-{child_number}"

                child_absolute_start = parent_start + child_start
                child_absolute_end = parent_start + child_end

                child_start_offset, child_end_offset = _source_offsets(
                    group,
                    child_absolute_start,
                    child_absolute_end,
                )

                chunks.append(
                    {
                        "chunk_key": child_key,
                        "parent_chunk_key": parent_key,
                        "page_start": page,
                        "page_end": page,
                        "section_path": section_path,
                        "heading_level": None,
                        "chunk_role": "content",
                        "table_id": None,
                        "text": child_text,
                        "text_for_embedding": (
                            f"Section: {section_path}\n{child_text}"
                        ),
                        "char_start": child_start_offset,
                        "char_end": child_end_offset,
                        "token_count": None,
                        "safety_scope": None,
                        "source_class": source_class,
                    }
                )

    return chunks
