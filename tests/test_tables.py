
import pymupdf

from noesis.ingest.tables import extract_tables


def test_extracts_synthetic_troubleshooting_table():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"

    tables = extract_tables(path)

    assert len(tables) == 1

    table = tables[0]
    assert table["table_id"] == "p5-t1"
    assert table["page"] == 5
    assert table["caption"] == (
        "Table 5.1 · Illustrative troubleshooting guide"
    )
    assert table["headers"] == [
        "Observed condition",
        "Possible area",
        "Next step",
    ]
    assert len(table["rows"]) == 3
    assert table["rows"][0] == [
        "Low discharge flow",
        "Supply or suction",
        "Check approved procedure",
    ]
    assert table["rows"][1][0] == "Elevated vibration"
    assert table["rows"][2][0] == "Seal-area leakage"


def test_pdf_without_tables_returns_empty_list(tmp_path):
    path = tmp_path / "no_table.pdf"

    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 80), "This page contains ordinary text.")
    document.save(path)
    document.close()

    assert extract_tables(path) == []


def test_missing_pdf_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        extract_tables("does-not-exist.pdf")
