
"""Detect document sections using PDF bookmarks and numbered headings."""

import re
from pathlib import Path
from typing import TypedDict

import pymupdf

from noesis.ingest.pdf import ExtractedLine


class Section(TypedDict):
    page: int
    title: str
    level: int
    section_path: str


class SectionLine(ExtractedLine):
    section_path: str
    heading_level: int | None


NUMBERED_HEADING = re.compile(
    r"^\s*(\d+(?:\.\d+){0,5})\.?\s+(.+?)\s*$"
)

DOTTED_NUMBER_TITLE = re.compile(
    r"^\s*\d+\.\s+"
)

PUBLICATION_METADATA = re.compile(
    r"^\s*(?:19|20)\d{2}\s+"
    r"\((?:revised|updated|reprint|edition)\)\s*$",
    re.IGNORECASE,
)


APPENDIX_HEADING = re.compile(
    r"^\s*APPENDIX\s+\d+\s*[-:–—]\s*\S.*$",
    re.IGNORECASE,
)

FIGURE_CAPTION_EXCLUSIONS = re.compile(
    r"^\s*(?:"
    r"\d{1,2}\s*:\s*(?:left|right)\s+hand\s+pump\b|"
    r"(?:left|right)\s+hand\s+pump\b|"
    r"group\s*$"
    r")",
    re.IGNORECASE,
)

FIGURE_CAPTION_EXCLUSIONS = re.compile(
    r"^\s*(?:"
    r"\d{1,2}\s*:\s*(?:left|right)\s+hand\s+pump\b|"
    r"(?:left|right)\s+hand\s+pump\b|"
    r"group\s*$"
    r")",
    re.IGNORECASE,
)


UNNUMBERED_HEADING_EXCLUSIONS = re.compile(
    r"^\s*(?:"
    r"authorized employee|affected employee|"
    r"capable of being locked out|energy source|"
    r"energy-isolating device|lockout device|tagout device|"
    r"energized|hot tap|setting up|"
    r"warning|caution|danger|notice|"
    r"table\s+\d+\s*[:.]|"
    r"figure\s+\d+\s*[:.]|"
    r"\d{1,2}\s*:\s*(?:left|right)\s+hand\s+pump\b|"
    r"(?:left|right)\s+hand\s+pump\b|"
    r"group\s*$|"
    r"equipment(?:\s+id)?\s*:|"
    r"document\s+(?:type|id)\s*:|"
    r"position\s*/\s*title|"
    r"group(?:\s+[SML])?\s*$|"
    r"reviewed\s+by(?:/date)?|"
    r"development\s+team|"
    r"service\s*:|"
    r"location\s*:|"
    r"inspection\s+(?:date|type)\s*:|"
    r"inspector\s*:|"
    r"observation\s*:|"
    r"potential\s+causes\s*:|"
    r"recommended\s+action\s*:|"
    r"priority\s*:|"
    r"shutdown\s+of\s+the\s+system\s+is\s+impractical|"
    r"region\s+[IVX]+|"
    r"\d+\s*[x\u00d7]\s*\d+(?:[-/][A-Za-z0-9]+)*|"
    r"\d+/\d+\s*[x\u00d7]\s*\d+[A-Za-z0-9]*|"
    r"[–—-]\s+|"
    r"\d{4}\s+\(|"
    r"IR\s+GUN|"
    r"OTHER\s*\(SPECIFY\)|"
    r"LOCATION|"
    r"JOB\s+STEPS"
    r")",
    re.IGNORECASE,
)

def _normalize_heading(text: str) -> str:
    """Normalize superficial punctuation and whitespace differences."""
    text = text.strip()
    text = re.sub(
        r"^\s*(\d+(?:\.\d+){0,5})\.?\s+",
        r"\1 ",
        text,
    )
    return re.sub(r"\s+", " ", text).casefold()
    
    


def _numbered_level(text: str) -> int | None:
    """Return the hierarchy level for a numbered heading."""
    match = NUMBERED_HEADING.match(text)
    if not match:
        return None
    return match.group(1).count(".") + 1


def _is_duplicate_dotted_title(
    text: str,
    page: int,
    lines: list[ExtractedLine],
) -> bool:
    """Identify dotted page titles duplicated by an undotted heading."""
    match = DOTTED_NUMBER_TITLE.match(text)
    if not match:
        return False

    undotted = re.sub(
        r"^(\s*\d+)\.\s+",
        r"\1 ",
        text,
        count=1,
    )
    undotted_normalized = _normalize_heading(undotted)

    return any(
        line["page"] == page
        and line["text"].strip() == undotted.strip()
        and _normalize_heading(line["text"]) == undotted_normalized
        for line in lines
    )  
    
def _body_font_size(lines: list[ExtractedLine]) -> float:
    """Estimate typical body-text size using the median font size."""
    sizes = []

    for line in lines:
        try:
            size = float(line.get("size") or 0)
        except (TypeError, ValueError):
            continue

        text = line["text"].strip()
        if size > 0 and len(text.split()) >= 5:
            sizes.append(size)

    if not sizes:
        return 0.0

    sizes.sort()
    return sizes[len(sizes) // 2]



def _detect_toc_pages(lines: list[ExtractedLine]) -> set[int]:
    """Identify pages containing repeated table-of-contents dot leaders."""
    leader_counts: dict[int, int] = {}

    for line in lines:
        if re.search(r"\.{3,}", line["text"]):
            page = line["page"]
            leader_counts[page] = leader_counts.get(page, 0) + 1

    return {
        page for page, count in leader_counts.items()
        if count >= 3
    }



def _split_heading_title(
    lines: list[ExtractedLine],
    index: int,
) -> tuple[int, str] | None:
    """Return the following title for a standalone numbered heading."""
    line = lines[index]
    number = line["text"].strip()

    if not re.fullmatch(r"\d+(?:\.\d+){1,5}\.?", number):
        return None

    try:
        size = float(line.get("size") or 0)
    except (TypeError, ValueError):
        return None

    if not line.get("bold") or size < 12:
        return None

    if index + 1 >= len(lines):
        return None

    following = lines[index + 1]
    title = following["text"].strip()

    if following["page"] != line["page"]:
        return None

    if not title or NUMBERED_HEADING.match(title):
        return None

    if not following.get("bold"):
        return None

    try:
        following_size = float(following.get("size") or 0)
    except (TypeError, ValueError):
        return None

    if following_size < 12:
        return None

    return number.rstrip("."), title




def _is_excluded_region(
    line: ExtractedLine,
    excluded_regions: list[
        tuple[int, tuple[float, float, float, float]]
    ],
) -> bool:
    """Return whether a line overlaps an excluded page-local region."""
    x0, y0, x1, y1 = line["bbox"]

    return any(
        line["page"] == page
        and x0 < bbox[2]
        and x1 > bbox[0]
        and y0 < bbox[3]
        and y1 > bbox[1]
        for page, bbox in excluded_regions
    )

    


def _is_footer_page_number(
    line: ExtractedLine,
    page_heights: dict[int, float],
) -> bool:
    text = line["text"].strip()

    if not re.fullmatch(r"\d{1,4}", text):
        return False

    try:
        y0 = float(line["bbox"][1])
        page_height = page_heights[line["page"]]
    except (KeyError, TypeError, ValueError, IndexError):
        return False

    return page_height > 0 and y0 >= 0.95 * page_height


    
def detect_sections(
    pdf_path: str | Path,
    lines: list[ExtractedLine],
     *,
    excluded_regions: list[
        tuple[int, tuple[float, float, float, float]]
    ] | None = None,
) -> list[SectionLine]:
    """Attach the active section path and heading level to each line.

    PDF bookmarks are preferred. Numbered headings are a fallback only
    when their typography and text provide sufficient evidence.
    """
    excluded_regions = excluded_regions or []
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    with pymupdf.open(path) as document:
      bookmarks = document.get_toc()
      page_heights = {
        page_number: float(page.rect.height)
        for page_number, page in enumerate(document, start=1)
    }

    bookmark_index: dict[tuple[int, str], int] = {}
    for level, title, page in bookmarks:
        bookmark_index[(page, _normalize_heading(title))] = level

    toc_pages = _detect_toc_pages(lines)
    active_titles: list[str] = []
    result: list[SectionLine] = []
    typical_body_size = _body_font_size(lines)
    split_title_indices = {
    index + 1
    for index in range(len(lines))
    if _split_heading_title(lines, index) is not None
    }

    for index, line in enumerate(lines):
        is_footer_number = _is_footer_page_number(line, page_heights)
        text = line["text"].strip()
        page = line["page"]
        normalized = _normalize_heading(text)
        is_excluded = _is_excluded_region(line, excluded_regions)
        split_heading = _split_heading_title(lines, index)
        is_dotted_number_title = _is_duplicate_dotted_title(
           text,
           page,
           lines,
        )
        is_publication_metadata = bool(PUBLICATION_METADATA.fullmatch(text))
        is_appendix_heading = bool(APPENDIX_HEADING.match(text))
        is_figure_caption = bool(FIGURE_CAPTION_EXCLUSIONS.match(text))
        # Bookmark matches are strongest, except duplicated dotted titles.
        
        # Bookmark matches are strongest, except excluded lines,
        # duplicated dotted titles, and publication metadata.
        level = None
        if (
            not is_excluded
            and not is_dotted_number_title
            and not is_publication_metadata
            and not is_footer_number
        ):
            level = bookmark_index.get((page, normalized))
        
        
        if (
            
            is_appendix_heading
            and not is_excluded
            and not is_dotted_number_title
            and not is_publication_metadata
            and not is_footer_number
            and not is_figure_caption
        ):
            level = 1
        # Use numbered-heading fallback only with heading-like typography.
        if (
            level is None
            and not is_excluded
            and page not in toc_pages
            and not is_dotted_number_title
            and not is_publication_metadata
            and split_heading is None
):
            match = NUMBERED_HEADING.match(text)
            if (match
                and not is_dotted_number_title
                and not is_publication_metadata
                and not is_figure_caption
            ):
                heading_text = match.group(2).strip()

                looks_like_toc_entry = bool(
                    re.search(r"\.{3,}", heading_text)
                )
                looks_like_sentence = (
                    len(heading_text.split()) > 12
                    or re.search(r"[.!?]\s", heading_text) is not None
                )

                try:
                    font_size = float(line.get("size") or 0)
                except (TypeError, ValueError):
                    font_size = 0

                numbered_subsection = bool(
    re.match(r"^\d+(?:\.\d+){2,}\s+\S", text)
)

                is_heading_styled = (
                    bool(line.get("bold"))
                    or font_size >= 12
                    or (
                        typical_body_size > 0
                        and font_size >= typical_body_size + 0.5
                    )
                    or numbered_subsection
                )
                
                if (
                    not looks_like_toc_entry
                    and not looks_like_sentence
                    and is_heading_styled
                ):
                    level = _numbered_level(text)

        if (
            level is None
            and not is_excluded
            and page not in toc_pages
            and not is_dotted_number_title
            and not is_publication_metadata
            and split_heading is None
            and index not in split_title_indices
        ):
            try:
                font_size = float(line.get("size") or 0)
            except (TypeError, ValueError):
                font_size = 0

            words = text.split()
            looks_like_heading = (
                bool(line.get("bold"))
                and 1 <= len(words) <= 12
                and len(text) <= 100
                and not re.search(r"[.!?]\s", text)
                and not text.endswith((".", ":", ";", ","))
                and not UNNUMBERED_HEADING_EXCLUSIONS.match(text)
                and not re.fullmatch(r"[A-Z]{1,2}", text.strip())
                and not text[:1].islower()
                and not is_figure_caption
            )

            if looks_like_heading:
               level = 1 if font_size >= 12 else 2
        if (
            split_heading is not None
            and not is_excluded
            and not is_footer_number
            and not is_figure_caption
        ):
            number, split_title = split_heading
            level = number.count(".") + 1
        if level is not None:        
            match = NUMBERED_HEADING.match(text)
            if split_heading is not None:
               title = f"{split_heading[0]} {split_heading[1]}"
            else:
               title = (
               f"{match.group(1)} {match.group(2)}"
               if match
               else text
              )

            active_titles = active_titles[: level - 1]
            active_titles.append(title)
            section_path = " > ".join(active_titles)
        elif is_dotted_number_title or is_publication_metadata or is_footer_number:
            # A dotted-number page title must not inherit a previous path.
            section_path = ""
        else:
            section_path = " > ".join(active_titles)

        result.append({
            **line,
            "section_path": section_path,
            "heading_level": level,
        })

    return result
