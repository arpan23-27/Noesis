
from noesis.ingest.pdf import extract_pdf
from noesis.ingest.sections import detect_sections
from noesis.ingest.warnings import extract_warnings


def test_extracts_synthetic_warning_block():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
    lines = detect_sections(path, extract_pdf(path))

    warnings = extract_warnings(lines)

    assert len(warnings) == 1

    warning = warnings[0]
    assert warning["label"] == "WARNING"
    assert warning["page_start"] == 2
    assert warning["page_end"] == 2
    assert warning["section_path"] == "2 Safety"
    assert "not an authorized safety procedure" in warning["text"]
    assert "perform assigned work." in warning["text"]
    assert warning["safety_scope"]
    assert warning["char_end"] >= warning["char_start"]


def test_ordinary_mention_of_warning_is_not_a_warning_block():
    path = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
    lines = detect_sections(path, extract_pdf(path))

    warnings = extract_warnings(lines)

    assert all("fixture tests PDF extraction" not in w["text"] for w in warnings)
