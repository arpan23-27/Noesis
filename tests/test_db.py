
import sqlite3

import pytest

from noesis.db import connect_db, init_db


def test_init_db_is_idempotent(tmp_path):
    path = tmp_path / "noesis.db"

    init_db(path)
    init_db(path)

    with connect_db(path) as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    assert {
        "documents",
        "chunks",
        "tags",
        "tag_aliases",
        "chunk_tags",
        "records",
    }.issubset(tables)


def test_invalid_source_class_is_rejected(tmp_path):
    path = tmp_path / "noesis.db"
    init_db(path)

    with connect_db(path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO documents (
                    filename, doc_type, source_class,
                    sha256, parse_version
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                ("manual.pdf", "oem_manual", "INVALID", "abc", "1"),
            )


def test_orphan_chunk_is_rejected(tmp_path):
    path = tmp_path / "noesis.db"
    init_db(path)

    with connect_db(path) as connection:
        assert connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO chunks (
                    doc_id, page_start, page_end, text, source_class
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (99999, 1, 1, "Orphan chunk", "APPROVED_DOC"),
            )


def test_foreign_keys_enabled_on_every_connection(tmp_path):
    path = tmp_path / "noesis.db"
    init_db(path)

    with connect_db(path) as first:
        assert first.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1

    with connect_db(path) as second:
        assert second.execute(
            "PRAGMA foreign_keys"
        ).fetchone()[0] == 1


def test_warning_requires_safety_scope(tmp_path):
    path = tmp_path / "noesis.db"
    init_db(path)

    with connect_db(path) as connection:
        doc_id = connection.execute(
            """
            INSERT INTO documents (
                filename, doc_type, source_class, sha256, parse_version
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            ("manual.pdf", "oem_manual", "APPROVED_DOC", "abc", "1"),
        ).lastrowid

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO chunks (
                    doc_id, page_start, page_end, text,
                    chunk_role, safety_scope, source_class
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id, 1, 1, "WARNING: example",
                    "warning", None, "APPROVED_DOC",
                ),
            )
