
import pytest

from noesis.tags import normalize_tag


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
