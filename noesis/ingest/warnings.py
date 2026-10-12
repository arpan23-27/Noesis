"""Extract standalone warning blocks from section-annotated PDF lines."""

import re
from typing import TypedDict

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


# Signal words are upper-case in the corpus. A label is the word alone on its
# line ("WARNING") or followed by ':' or '!' ("WARNING: Hot surface"). Requiring
# that keeps prose such as "DANGER tag must be attached" out.
WARNING_LABEL = re.compile(
    r"^\s*(WARNING|CAUTION|DANGER|NOTICE)\s*(?:[:!]\s*|$)(.*)$"
)

# Legends define the signal words ("WARNING: Indicates a hazardous
# situation ..."). They describe the manual, not the equipment.
LEGEND_SECTION = re.compile(
    r"\b(definitions?|symbols?|signal words?|legend)\b", re.IGNORECASE
)

# A numbered step ("5." or "1. Remove the cover") is procedure text, not part
# of the notice before it.
STEP_MARKER = re.compile(r"^\s*\d{1,2}[.)](?:\s|$)")

# Backstop: genuine warnings in the corpus are under ~700 characters. A block
# stops at the last line that fits; the rest stays ordinary content.
MAX_WARNING_CHARS = 800


def extract_warnings(lines: list[SectionLine]) -> list[WarningBlock]:
    """Extract WARNING/CAUTION/DANGER/NOTICE blocks and their following text.

    A block ends at the next heading, another warning label, a numbered step,
    a section or page change, or the length cap. Offsets refer to the label
    line and the final captured line, and are only meaningful within a single
    page. `safety_scope` is the section path the warning applies to. Warnings
    inside signal-word legends are skipped.
    """
    warnings: list[WarningBlock] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        label_match = WARNING_LABEL.match(line["text"])

        if not label_match:
            index += 1
            continue

        label = label_match.group(1)
        page = line["page"]
        section_path = line["section_path"]
        first = label_match.group(2).strip()
        captured = [first] if first else []
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

            if STEP_MARKER.match(candidate["text"]):
                break

            # Don't let a warning absorb text from another section.
            if candidate["section_path"] != section_path:
                break

            piece = candidate["text"].strip()

            if captured and len(" ".join(captured + [piece])) > MAX_WARNING_CHARS:
                break

            captured.append(piece)
            end_line = candidate
            cursor += 1

        text = " ".join(part for part in captured if part).strip()
        leaf = section_path.split(" > ")[-1]

        if text and not LEGEND_SECTION.search(leaf):
            warnings.append(
                {
                    "page_start": page,
                    "page_end": page,
                    "section_path": section_path,
                    "label": label,
                    "text": text,
                    "safety_scope": section_path,
                    "char_start": line["char_start"],
                    "char_end": end_line["char_end"],
                }
            )

        index = max(cursor, index + 1)

    return warnings