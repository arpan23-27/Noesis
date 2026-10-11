import pymupdf
import pytest

from noesis.ingest.tables import (
    clean_cell,
    extract_tables,
    looks_like_header,
    rejection_reason,
    row_sentence,
    row_text,
    table_rows,
)

SYNTHETIC = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"


def make_table():
    return {
        "table_id": "p1-t1",
        "page": 1,
        "bbox": (0.0, 0.0, 1.0, 1.0),
        "caption": "Table 6.1 Trouble check list",
        "headers": ["Symptom", "Cause", "Remedy"],
        "rows": [
            ["No water delivered", "Air leak", "Tighten suction joints"],
            ["", "Impeller blocked", "Clear the impeller"],
            ["Symptom", "Cause", "Remedy"],
            ["", "", ""],
        ],
    }


def test_extracts_synthetic_troubleshooting_table():
    rejected = []
    tables = extract_tables(SYNTHETIC, rejected)

    assert len(tables) == 1
    assert rejected == []

    table = tables[0]
    assert table["table_id"] == "p5-t1"
    assert table["page"] == 5
    assert table["caption"].startswith("Table 5.1")
    assert table["caption"].endswith("Illustrative troubleshooting guide")
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
    with pytest.raises(FileNotFoundError):
        extract_tables("does-not-exist.pdf")


def test_single_row_detection_is_rejected():
    assert rejection_reason([["x" * 500, "", ""]]) == "too_few_rows"


def test_short_table_of_long_prose_is_rejected():
    matrix = [["word " * 100, ""], ["more " * 100, ""]]
    assert rejection_reason(matrix) == "page_prose"


def test_warning_box_is_rejected():
    matrix = [
        ["WARNING", "", "NEVER APPLY HEAT"],
        ["", "", "It may explode"],
        ["WARNING", "", "Lock out power"],
    ]
    assert rejection_reason(matrix) == "warning_box"


def test_real_table_is_kept():
    matrix = [
        ["Symptom", "Cause", "Remedy"],
        ["No water", "Air leak", "Fix joints"],
        ["Low flow", "Blocked", "Clean"],
    ]
    assert rejection_reason(matrix) is None


def test_wide_matrix_is_not_mistaken_for_a_warning_box():
    matrix = [["WARNING"] + ["x"] * 9, ["a"] * 10, ["b"] * 10]
    assert rejection_reason(matrix) is None


def test_header_detection():
    assert looks_like_header(["LOCATION", "JOB STEPS"])
    assert looks_like_header(["", "", "2x3-11"])
    assert not looks_like_header(["", "\u2022 List the lubricant"])
    assert not looks_like_header(["", "for similar applications"])
    assert not looks_like_header(["", ""])


def test_clean_cell():
    assert clean_cell("\uf0b7  List\nthe oil") == "\u2022 List the oil"
    assert clean_cell(None) == ""


def test_table_rows_fill_blank_symptom_and_drop_noise():
    assert table_rows(make_table()) == [
        ["No water delivered", "Air leak", "Tighten suction joints"],
        ["No water delivered", "Impeller blocked", "Clear the impeller"],
    ]


def test_row_sentence_and_text_carry_caption_and_headers():
    table = make_table()
    row = table_rows(table)[1]

    assert row_sentence(table, row) == (
        "Table 6.1 Trouble check list. Symptom: No water delivered; "
        "Cause: Impeller blocked; Remedy: Clear the impeller."
    )
    assert row_text(table, row) == (
        "Table 6.1 Trouble check list\n"
        "Symptom | Cause | Remedy\n"
        "No water delivered | Impeller blocked | Clear the impeller"
    )