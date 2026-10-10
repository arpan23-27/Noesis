
import re
import unicodedata


TYPE_WORDS = {
    "pump": "P",
    "motor": "M",
    "flow indicating controller": "FIC",
    "pressure indicator": "PI",
    "temperature indicator": "TI",
    "valve": "V",
}

# Only these canonical prefixes are accepted.
ALLOWED_PREFIXES = {"P", "M", "FIC", "PI", "TI", "V"}

# Prefix + exactly three digits + optional single-letter suffix.
TAG_PATTERN = re.compile(r"^([A-Z]+)(\d{3})([A-Z]?)$")


def normalize_tag(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    value = unicodedata.normalize("NFKC", value).upper()
    value = re.sub(r"[\u2010-\u2015\u2212_]", " ", value)
    value = re.sub(r"[\s-]+", "", value)

    # Map recognized equipment-type words before validating the prefix.
    for word, prefix in sorted(
        TYPE_WORDS.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        normalized_word = word.upper().replace(" ", "")
        if value.startswith(normalized_word):
            value = prefix + value[len(normalized_word):]
            break

    match = TAG_PATTERN.fullmatch(value)
    if not match:
        return None

    prefix, number, suffix = match.groups()

    # Validate the canonical prefix after type-word mapping.
    if prefix not in ALLOWED_PREFIXES:
        return None

    return f"{prefix}{number}{suffix}"
