from noesis.ingest.tagging import persist_chunk_tags
from noesis.ingest.chunking import DEFAULT_CHILD_SIZE, DEFAULT_OVERLAP, DEFAULT_PARENT_SIZE
"""Idempotent PDF ingestion and SQLite persistence."""

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf

from noesis.db import DEFAULT_DB_PATH, connect_db, init_db
from noesis.ingest.assembly import assemble_document

DEFAULT_PARSE_VERSION = "1"


def _sha256_file(path: Path) -> str:
    """Calculate a file's SHA-256 digest without loading it all into memory."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def _is_unchanged(
    connection: sqlite3.Connection,
    filename: str,
    sha256: str,
    parse_version: str,
) -> sqlite3.Row | None:
    """Return the existing document if its content and parser version match."""
    row = connection.execute(
        """
        SELECT doc_id, sha256, parse_version
        FROM documents
        WHERE filename = ?
        """,
        (filename,),
    ).fetchone()

    if (
        row is not None
        and row["sha256"] == sha256
        and row["parse_version"] == parse_version
    ):
        return row

    return None


def _insert_chunk(
    connection: sqlite3.Connection,
    chunk: dict[str, Any],
    doc_id: int,
    parent_id: int | None,
) -> int:
    """Insert one chunk and return its SQLite ID."""
    cursor = connection.execute(
        """
        INSERT INTO chunks (
            doc_id, parent_chunk_id, page_start, page_end,
            section_path, heading_level, chunk_role, table_id,
            text, text_for_embedding, char_start, char_end,
            token_count, safety_scope, source_class
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc_id,
            parent_id,
            chunk["page_start"],
            chunk["page_end"],
            chunk["section_path"],
            chunk["heading_level"],
            chunk["chunk_role"],
            chunk["table_id"],
            chunk["text"],
            chunk["text_for_embedding"],
            chunk["char_start"],
            chunk["char_end"],
            chunk["token_count"],
            chunk["safety_scope"],
            chunk["source_class"],
        ),
    )
    return int(cursor.lastrowid)


def ingest_pdf(
    pdf_path: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB_PATH,
    doc_type: str = "oem_manual",
    source_class: str = "APPROVED_DOC",
    parse_version: str = DEFAULT_PARSE_VERSION,
    parent_size: int = DEFAULT_PARENT_SIZE,
    child_size: int = DEFAULT_CHILD_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> dict[str, Any]:
    """Ingest a PDF, skipping unchanged documents.

    A changed document is assembled before the write transaction begins.
    Document metadata and replacement chunks are committed atomically.
    """
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    if source_class not in {"APPROVED_DOC", "RECORD"}:
        raise ValueError(f"Invalid source_class: {source_class!r}")

    if not parse_version.strip():
        raise ValueError("parse_version must not be empty")

    digest = _sha256_file(path)
    filename = path.name

    with pymupdf.open(path) as document:
        if document.is_encrypted:
            raise ValueError(f"Encrypted PDFs are unsupported: {path}")
        page_count = len(document)

    database = Path(db_path)
    init_db(database)

    # Fast path: avoid PDF assembly for an unchanged document.
    connection = connect_db(database)
    try:
        unchanged = _is_unchanged(
            connection, filename, digest, parse_version
        )
        if unchanged is not None:
            return {
                "status": "skipped",
                "doc_id": unchanged["doc_id"],
                "filename": filename,
                "sha256": digest,
                "pages": page_count,
                "chunks": 0,
            }
    finally:
        connection.close()

    # Build the replacement before modifying stored data.
    chunks = assemble_document(
        path,
        parent_size=parent_size,
        child_size=child_size,
        overlap=overlap,
        source_class=source_class,
    )
    
    if not chunks:
        raise ValueError(
            f"No chunks assembled from PDF: {path}. "
            "Existing database records have not been modified."
        )

    connection = connect_db(database)

    try:
        connection.execute("BEGIN IMMEDIATE")

        # Recheck after obtaining the write lock.
        unchanged = _is_unchanged(
            connection, filename, digest, parse_version
        )
        
        if unchanged is not None:
            connection.commit()
            return {
                "status": "skipped",
                "doc_id": unchanged["doc_id"],
                "filename": filename,
                "sha256": digest,
                "pages": page_count,
                "chunks": 0,
            }


        existing = connection.execute(
            "SELECT doc_id FROM documents WHERE filename = ?",
            (filename,),
        ).fetchone()

        ingested_at = datetime.now(timezone.utc).isoformat()

        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    filename, doc_type, source_class, sha256,
                    pages, ingested_at, parse_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    doc_type,
                    source_class,
                    digest,
                    page_count,
                    ingested_at,
                    parse_version,
                ),
            )
            doc_id = int(cursor.lastrowid)
        else:
            doc_id = int(existing["doc_id"])

            # Cascading foreign keys remove old chunks and their children.
            connection.execute(
                "DELETE FROM chunks WHERE doc_id = ?",
                (doc_id,),
            )

            connection.execute(
                """
                UPDATE documents
                SET doc_type = ?, source_class = ?, sha256 = ?,
                    pages = ?, ingested_at = ?, parse_version = ?
                WHERE doc_id = ?
                """,
                (
                    doc_type,
                    source_class,
                    digest,
                    page_count,
                    ingested_at,
                    parse_version,
                    doc_id,
                ),
            )

        
        chunk_ids: dict[str, int] = {}

        # Insert root chunks first so parent IDs exist before child inserts.
        for chunk in chunks:
            if chunk["parent_chunk_key"] is None:
                chunk_ids[chunk["chunk_key"]] = _insert_chunk(
                    connection, chunk, doc_id, None
                )

        # Insert children after their parents.
        for chunk in chunks:
            parent_key = chunk["parent_chunk_key"]
            if parent_key is None:
                continue

            parent_id = chunk_ids.get(parent_key)
            if parent_id is None:
                raise ValueError(
                    f"Missing parent chunk {parent_key!r} "
                    f"for {chunk['chunk_key']!r}"
                )

            chunk_ids[chunk["chunk_key"]] = _insert_chunk(
                connection, chunk, doc_id, parent_id
            )

        # Persist tags after every chunk has a database ID.
        persisted_tag_links = persist_chunk_tags(
            connection,
            chunks,
            chunk_ids,
        )

        connection.commit()

        return {
            "status": "ingested" if existing is None else "reingested",
            "doc_id": doc_id,
            "filename": filename,
            "sha256": digest,
            "pages": page_count,
            "chunks": len(chunks),
            "tag_links": persisted_tag_links,
        }

        

    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
