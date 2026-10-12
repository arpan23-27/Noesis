from noesis.ingest.chunking import (
    CHILD_TOKENS,
    PARENT_TOKENS,
    _split_text,
    approx_tokens,
    chunk_lines,
)

PATH = "3 Maintenance > 3.2 Bearings"
SENTENCE = "Inspect the bearing housing for heat and record the result. "


def make_lines(count=120):
    lines, offset = [], 0
    for i in range(count):
        text = f"Item {i}. Inspect the bearing housing for heat and record it."
        lines.append(
            {
                "page": 1,
                "text": text,
                "section_path": PATH,
                "heading_level": None,
                "char_start": offset,
                "char_end": offset + len(text),
                "bbox": (0.0, 0.0, 1.0, 1.0),
            }
        )
        offset += len(text) + 1
    return lines


def test_approx_tokens():
    assert approx_tokens("") == 1
    assert approx_tokens("x" * 400) == 100


def test_every_chunk_has_a_token_count():
    for chunk in chunk_lines(make_lines()):
        assert chunk["token_count"] == approx_tokens(chunk["text"])


def test_children_and_parents_fit_their_budgets_and_link_up():
    chunks = chunk_lines(make_lines())
    parents = {c["chunk_key"]: c for c in chunks if c["chunk_role"] == "parent"}
    children = [c for c in chunks if c["chunk_role"] == "content"]

    assert len(parents) >= 2
    assert len(children) >= 6

    for parent in parents.values():
        assert parent["token_count"] <= PARENT_TOKENS

    for child in children:
        assert child["token_count"] <= CHILD_TOKENS
        assert child["parent_chunk_key"] in parents


def test_split_respects_size_and_covers_every_character():
    text = (SENTENCE * 30).strip()
    covered = set()

    for start, end in _split_text(text, 300, 130):
        assert end - start <= 300
        covered.update(range(start, end))

    missing = [
        i for i, ch in enumerate(text) if not ch.isspace() and i not in covered
    ]
    assert missing == []


def test_split_ends_chunks_on_sentence_boundaries():
    text = (SENTENCE * 30).strip()

    for start, end in _split_text(text, 300, 130)[:-1]:
        assert text[start:end].rstrip().endswith(".")