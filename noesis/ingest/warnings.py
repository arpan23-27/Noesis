
"""Extract standalone warning blocks from section-annotated PDF lines."""

import re
from typing import TypedDict

from noesis.ingest.pdf import ExtractedLine
from noesis.ingest.sections import SectionLine


class WarningBlock(TypedDict):
    page_start: int
    page_end: int
    section_path: str
    label: str
    text: str
    safety_scope: str
    char_start: int
    char_end: int


WARNING_LABEL = re.compile(r"^\s*(WARNING|DANGER)\s*[:!]?\s*$", re.IGNORECASE)


def extract_warnings(lines: list[SectionLine]) -> list[WarningBlock]:
    """Extract standalone WARNING/DANGER labels and their following text.

    A block ends at the next recognized section heading, another standalone
    warning label, or a page change. Offsets refer to the label line and the
    final captured line, and are only meaningful within a single page.
    """
    warnings: list[WarningBlock] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        label_match = WARNING_LABEL.match(line["text"])

        if not label_match:
            index += 1
            continue

        label = label_match.group(1).upper()
        page = line["page"]
        section_path = line["section_path"]
        captured = []
        end_line = line
        cursor = index + 1

        while cursor < len(lines):
            candidate = lines[cursor]

            if candidate["page"] != page:
                break

            if candidate["heading_level"] is not None:
                break

            if WARNING_LABEL.match(candidate["text"]):
                break

            # Don't let a warning absorb text from another section.
            if candidate["section_path"] != section_path:
                break

            captured.append(candidate["text"].strip())
            end_line = candidate
            cursor += 1

        text = " ".join(part for part in captured if part).strip()

        if text:
            warnings.append(
                {
                    "page_start": page,
                    "page_end": page,
                    "section_path": section_path,
                    "label": label,
                    "text": text,
                    "safety_scope": (
                        f"Documented {label.lower()} in section "
                        f"{section_path}"
                    ),
                    "char_start": line["char_start"],
                    "char_end": end_line["char_end"],
                }
            )

        index = max(cursor, index + 1)

    return warnings
