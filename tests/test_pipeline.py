
import pytest

from noesis.db import connect_db
from noesis.ingest import pipeline
from noesis.ingest.pipeline import ingest_pdf


PDF_PATH = "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"


def test_first_ingestion_persists_document_and_chunks(tmp_path):
    db_path = tmp_path / "noesis.db"

    result = ingest_pdf(PDF_PATH, db_path=db_path)

    assert result["status"] == "ingested"
    assert result["pages"] == 7
    assert result["chunks"] == 66

    with connect_db(db_path) as connection:
        document = connection.execute(
            "SELECT * FROM documents WHERE filename = ?",
            ("Synthetic_Centrifugal_Pump_Manual.pdf",),
        ).fetchone()

        assert document is not None
        assert document["sha256"] == result["sha256"]

        counts = connection.execute(
            """
            SELECT chunk_role, COUNT(*) AS count
            FROM chunks
            WHERE doc_id = ?
            GROUP BY chunk_role
            """,
            (document["doc_id"],),
        ).fetchall()

        roles = {row["chunk_role"]: row["count"] for row in counts}

        assert roles == {
            "content": 32,
            "parent": 32,
            "table": 1,
            "warning": 1,
        }


def test_unchanged_document_is_skipped(tmp_path):
    db_path = tmp_path / "noesis.db"

    first = ingest_pdf(PDF_PATH, db_path=db_path)
    second = ingest_pdf(PDF_PATH, db_path=db_path)

    assert first["status"] == "ingested"
    assert second["status"] == "skipped"
    assert second["doc_id"] == first["doc_id"]
    assert second["chunks"] == 0

    with connect_db(db_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id = ?",
            (first["doc_id"],),
        ).fetchone()[0]

    assert count == 66


def test_parser_version_change_triggers_reingestion(tmp_path):
    db_path = tmp_path / "noesis.db"

    first = ingest_pdf(
        PDF_PATH, db_path=db_path, parse_version="1"
    )
    second = ingest_pdf(
        PDF_PATH, db_path=db_path, parse_version="2"
    )

    assert second["status"] == "reingested"
    assert second["doc_id"] == first["doc_id"]

    with connect_db(db_path) as connection:
        document = connection.execute(
            "SELECT parse_version FROM documents WHERE doc_id = ?",
            (first["doc_id"],),
        ).fetchone()

        count = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id = ?",
            (first["doc_id"],),
        ).fetchone()[0]

    assert document["parse_version"] == "2"
    assert count == 66


def test_parent_child_relationships_are_persisted(tmp_path):
    db_path = tmp_path / "noesis.db"
    result = ingest_pdf(PDF_PATH, db_path=db_path)

    with connect_db(db_path) as connection:
        children = connection.execute(
            """
            SELECT COUNT(*)
            FROM chunks AS child
            JOIN chunks AS parent
              ON child.parent_chunk_id = parent.chunk_id
            WHERE child.doc_id = ?
              AND parent.doc_id = ?
            """,
            (result["doc_id"], result["doc_id"]),
        ).fetchone()[0]

    assert children == 32


def test_failed_reingestion_rolls_back_existing_chunks(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "noesis.db"
    first = ingest_pdf(PDF_PATH, db_path=db_path)

    def broken_assembly(*args, **kwargs):
        return [{"chunk_key": "invalid", "parent_chunk_key": None}]

    monkeypatch.setattr(pipeline, "assemble_document", broken_assembly)

    with pytest.raises(KeyError):
        ingest_pdf(
            PDF_PATH,
            db_path=db_path,
            parse_version="2",
        )

    with connect_db(db_path) as connection:
        document = connection.execute(
            "SELECT parse_version FROM documents WHERE doc_id = ?",
            (first["doc_id"],),
        ).fetchone()

        count = connection.execute(
            "SELECT COUNT(*) FROM chunks WHERE doc_id = ?",
            (first["doc_id"],),
        ).fetchone()[0]

    assert document["parse_version"] == "1"
    assert count == 66
