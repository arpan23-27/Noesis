
from noesis.ingest.tagging import discover_chunk_tags


def make_chunk(key, text):
    return {
        "chunk_key": key,
        "parent_chunk_key": None,
        "page_start": 1,
        "page_end": 1,
        "section_path": "1 Example",
        "heading_level": None,
        "chunk_role": "content",
        "table_id": None,
        "text": text,
        "text_for_embedding": text,
        "char_start": None,
        "char_end": None,
        "token_count": None,
        "safety_scope": None,
        "source_class": "APPROVED_DOC",
    }


def test_equivalent_tag_spellings_resolve_to_one_canonical_tag():
    chunks = [
        make_chunk("a", "Inspect P-101A during maintenance."),
        make_chunk("b", "Related equipment: P 101 A."),
        make_chunk("c", "The identifier is p101a."),
    ]

    result = discover_chunk_tags(chunks)

    assert result == {
        "a": {"P101A"},
        "b": {"P101A"},
        "c": {"P101A"},
    }


def test_distinct_suffixes_remain_distinct():
    chunks = [
        make_chunk("a", "Inspect P-101A."),
        make_chunk("b", "Inspect P-101B."),
    ]

    result = discover_chunk_tags(chunks)

    assert result["a"] == {"P101A"}
    assert result["b"] == {"P101B"}


def test_unsupported_standard_number_is_not_a_tag():
    chunks = [make_chunk("a", "Refer to API 610 and ISO 9001.")]

    assert discover_chunk_tags(chunks) == {}


def test_multiple_equipment_tags_in_one_chunk():
    chunks = [
        make_chunk("a", "Pump P-101A is driven by motor M-201.")
    ]

    assert discover_chunk_tags(chunks) == {
        "a": {"M201", "P101A"}
    }
