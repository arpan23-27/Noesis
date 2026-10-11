
import pytest

from noesis.ingest.chunking import _split_text, chunk_lines
from noesis.ingest.pdf import extract_pdf
from noesis.ingest.sections import detect_sections


def test_split_text_respects_size_and_overlap():
    text = "alpha beta gamma delta epsilon zeta eta theta"

    ranges = _split_text(text, target_size=20, overlap=5)

    assert len(ranges) > 1
    assert all(start < end for start, end in ranges)
    assert all(end - start <= 20 for start, end in ranges)

    # The ranges should overlap, rather than leaving gaps.
    for previous, current in zip(ranges, ranges[1:]):
        assert current[0] < previous[1]


def test_chunking_preserves_parent_child_relationships():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
    lines = detect_sections(path, extract_pdf(path))

    chunks = chunk_lines(
        lines,
        parent_size=500,
        child_size=180,
        overlap=25,
    )

    parents = {
        chunk["chunk_key"]: chunk
        for chunk in chunks
        if chunk["chunk_role"] == "parent"
    }
    children = [
        chunk for chunk in chunks
        if chunk["parent_chunk_key"] is not None
    ]

    assert parents
    assert children

    for child in children:
        assert child["parent_chunk_key"] in parents

        parent = parents[child["parent_chunk_key"]]
        assert child["section_path"] == parent["section_path"]
        assert child["page_start"] == parent["page_start"]
        assert child["page_end"] == parent["page_end"]


def test_chunks_do_not_cross_page_or_section_boundaries():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
    lines = detect_sections(path, extract_pdf(path))

    chunks = chunk_lines(lines)

    for chunk in chunks:
        assert chunk["page_start"] == chunk["page_end"]
        assert chunk["section_path"]


def test_invalid_chunk_settings_raise():
    with pytest.raises(ValueError):
        _split_text("some text", target_size=0, overlap=0)

    with pytest.raises(ValueError):
        chunk_lines([], child_size=100, overlap=100)


def test_embedding_text_contains_section_context():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
    lines = detect_sections(path, extract_pdf(path))

    chunks = chunk_lines(lines)

    for chunk in chunks:
        assert chunk["section_path"] in chunk["text_for_embedding"]
