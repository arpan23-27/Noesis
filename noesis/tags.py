
import re
import unicodedata


TYPE_WORDS = {
    "pump": "P",
    "motor": "M",
}

TAG_PATTERN = re.compile(r"^([A-Z])(\d{3})([A-Z])$")


def normalize_tag(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    # Normalize Unicode compatibility characters, including
    # full-width characters and non-breaking hyphens.
    value = unicodedata.normalize("NFKC", value).upper()

    # Treat Unicode dash variants and underscores as separators.
    value = re.sub(r"[\u2010-\u2015\u2212_]", " ", value)
    value = re.sub(r"[\s-]+", "", value)

    # Remove a recognized equipment type word.
    for word, prefix in TYPE_WORDS.items():
        if value.startswith(word.upper()):
            value = prefix + value[len(word):]
            break

    match = TAG_PATTERN.fullmatch(value)

    if not match:
        return None

    return "".join(match.groups())
