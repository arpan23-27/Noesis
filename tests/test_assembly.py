import pymupdf

from noesis.ingest.assembly import assemble_document


PDF_PATH = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"


def test_assembly_emits_one_warning_and_one_table():
    chunks = assemble_document(PDF_PATH)

    warnings = [c for c in chunks if c["chunk_role"] == "warning"]
    tables = [c for c in chunks if c["chunk_role"] == "table"]

    assert len(warnings) == 1
    assert len(tables) == 1

    warning = warnings[0]
    assert warning["page_start"] == 2
    assert warning["section_path"] == "2 Safety"
    assert warning["safety_scope"]
    assert warning["text"].startswith("WARNING:")

    table = tables[0]
    assert table["page_start"] == 5
    assert table["table_id"] == "p5-t1"
    assert "Observed condition | Possible area | Next step" in table["text"]
    assert "Low discharge flow | Supply or suction | Check approved procedure" in (
        table["text"]
    )


def test_specialized_content_is_not_duplicated_as_ordinary_content():
    chunks = assemble_document(PDF_PATH)

    content = [
        c["text"]
        for c in chunks
        if c["chunk_role"] in {"parent", "content"}
    ]
    ordinary_text = "\n".join(content)

    assert "This synthetic document is not an authorized safety procedure." not in (
        ordinary_text
    )
    assert "Low discharge flow | Supply or suction | Check approved procedure" not in (
        ordinary_text
    )


def test_every_chunk_has_valid_page_and_section_context():
    chunks = assemble_document(PDF_PATH)

    assert chunks

    for chunk in chunks:
        assert chunk["page_start"] >= 1
        assert chunk["page_end"] >= chunk["page_start"]
        assert chunk["section_path"]
        assert chunk["text"].strip()

    for chunk in chunks:
        if chunk["chunk_role"] == "warning":
            assert chunk["safety_scope"] is not None
            assert chunk["safety_scope"].strip()


def test_source_class_is_preserved():
    chunks = assemble_document(PDF_PATH, source_class="RECORD")

    assert chunks
    assert all(chunk["source_class"] == "RECORD" for chunk in chunks)

def test_every_assembled_chunk_has_complete_schema():
    chunks = assemble_document(PDF_PATH)

    required_fields = {
        "chunk_key",
        "parent_chunk_key",
        "page_start",
        "page_end",
        "section_path",
        "heading_level",
        "chunk_role",
        "table_id",
        "text",
        "text_for_embedding",
        "char_start",
        "char_end",
        "token_count",
        "safety_scope",
        "source_class",
    }

    assert chunks

    for chunk in chunks:
        assert required_fields <= chunk.keys(), (
            f"{chunk['chunk_key']} is missing fields: "
            f"{required_fields - chunk.keys()}"
        )
def test_warning_offsets_point_to_original_warning_block():
    chunks = assemble_document(PDF_PATH)
    warning = next(c for c in chunks if c["chunk_role"] == "warning")

    with pymupdf.open(PDF_PATH) as doc:
        page_text = doc[warning["page_start"] - 1].get_text("text")

    source_slice = page_text[warning["char_start"]:warning["char_end"]]

    assert source_slice.startswith("WARNING")
    assert "not an authorized safety procedure" in source_slice
    assert "follow applicable site rules" in source_slice
    

def test_table_inherits_section_from_previous_page_when_needed():
    from noesis.ingest.assembly import _table_section

    table = {
        "page": 4,
        "bbox": (50.0, 50.0, 500.0, 300.0),
    }

    lines = [
        {
            "page": 3,
            "bbox": (50.0, 100.0, 500.0, 120.0),
            "section_path": "2 Vibration > 2.2 Bearing defects",
        },
        {
            "page": 4,
            "bbox": (50.0, 350.0, 500.0, 370.0),
            "section_path": "3 Maintenance",
        },
    ]

    assert _table_section(table, lines) == (
        "2 Vibration > 2.2 Bearing defects"
    )
