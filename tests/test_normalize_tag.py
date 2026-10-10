
import pytest

from noesis.normalize import normalize_tag


@pytest.mark.parametrize(
    "value",
    [
        "P-101A",
        "P101A",
        "p-101a",
        "P 101 A",
        "pump 101A",
        "Pump-101-A",
        "P–101A",
        "P‑101A",
        "P_101A",
        "P-101 A",
    ],
)
def test_valid_tags_normalize_to_canonical_form(value):
    assert normalize_tag(value) == "P101A"


@pytest.mark.parametrize(
    "value",
    [
        "API 610",
        "ISO 9001",
        "hello",
        "101",
        "P-1",
        "P-101AB",
        "",
    ],
)
def test_invalid_tags_return_none(value):
    assert normalize_tag(value) is None


def test_distinct_tags_remain_distinct():
    assert normalize_tag("P-101A") == "P101A"
    assert normalize_tag("P-101B") == "P101B"
    assert normalize_tag("P-102A") == "P102A"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("P-101", "P101"),
        ("P-101A", "P101A"),
        ("P-101B", "P101B"),
        ("M-201", "M201"),
        ("FIC-203", "FIC203"),
        ("PI-204", "PI204"),
        ("TI-205", "TI205"),
        ("V-301", "V301"),
    ],
)
def test_supported_equipment_tags(raw, expected):
    assert normalize_tag(raw) == expected
def test_tag_without_suffix_differs_from_tag_with_suffix():
    assert normalize_tag("P-101") != normalize_tag("P-101A")
