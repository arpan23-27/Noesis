
import pymupdf
import pytest

from noesis.ingest.pdf import extract_pdf


def create_test_pdf(path):
    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 80),
        "3 Maintenance",
        fontsize=16,
        fontname="hebo",
    )
    page.insert_text(
        (72, 110),
        "Inspect bearing condition.",
        fontsize=10,
        fontname="helv",
    )

    document.save(path)
    document.close()


def test_extracts_line_text_and_layout(tmp_path):
    path = tmp_path / "fixture.pdf"
    create_test_pdf(path)

    lines = extract_pdf(path)

    assert len(lines) == 2
    assert lines[0]["page"] == 1
    assert lines[0]["text"] == "3 Maintenance"
    assert lines[0]["size"] == 16
    assert lines[0]["bold"] is True
    assert len(lines[0]["bbox"]) == 4

    assert lines[1]["text"] == "Inspect bearing condition."
    assert lines[1]["size"] == 10
    assert lines[1]["bold"] is False


def test_offsets_match_page_text(tmp_path):
    path = tmp_path / "fixture.pdf"
    create_test_pdf(path)

    lines = extract_pdf(path)

    with pymupdf.open(path) as document:
        page_text = document[0].get_text("text")

    for line in lines:
        start = line["char_start"]
        end = line["char_end"]

        assert page_text[start:end] == line["text"]
        assert 0 <= start < end <= len(page_text)


def test_missing_pdf_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf(tmp_path / "missing.pdf")
