
"""SQLite schema and connection management for Noesis."""

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path("data/noesis.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    doc_type TEXT NOT NULL,
    source_class TEXT NOT NULL
        CHECK (source_class IN ('APPROVED_DOC', 'RECORD')),
    sha256 TEXT NOT NULL,
    pages INTEGER CHECK (pages IS NULL OR pages >= 0),
    ingested_at TEXT,
    parse_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER PRIMARY KEY,
    doc_id INTEGER NOT NULL,
    parent_chunk_id INTEGER,
    page_start INTEGER NOT NULL CHECK (page_start >= 1),
    page_end INTEGER NOT NULL CHECK (page_end >= page_start),
    section_path TEXT,
    heading_level INTEGER,
    chunk_role TEXT NOT NULL DEFAULT 'content',
    table_id TEXT,
    text TEXT NOT NULL,
    text_for_embedding TEXT,
    char_start INTEGER,
    char_end INTEGER,
    token_count INTEGER CHECK (
        token_count IS NULL OR token_count >= 0
    ),
    safety_scope TEXT,
    source_class TEXT NOT NULL
        CHECK (source_class IN ('APPROVED_DOC', 'RECORD')),

    FOREIGN KEY (doc_id)
        REFERENCES documents(doc_id) ON DELETE CASCADE,

    FOREIGN KEY (parent_chunk_id)
        REFERENCES chunks(chunk_id) ON DELETE CASCADE,

    CHECK (parent_chunk_id IS NULL OR parent_chunk_id <> chunk_id),
    CHECK (
        (char_start IS NULL AND char_end IS NULL)
        OR (
            char_start IS NOT NULL
            AND char_end IS NOT NULL
            AND char_start >= 0
            AND char_end >= char_start
        )
    ),
    CHECK (
        chunk_role <> 'warning' OR safety_scope IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_pages
    ON chunks(doc_id, page_start, page_end);

CREATE INDEX IF NOT EXISTS idx_chunks_parent
    ON chunks(parent_chunk_id);

CREATE TABLE IF NOT EXISTS tags (
    tag_id INTEGER PRIMARY KEY,
    canonical TEXT NOT NULL UNIQUE,
    equipment_type TEXT
);

CREATE TABLE IF NOT EXISTS tag_aliases (
    tag_id INTEGER NOT NULL,
    surface_form TEXT NOT NULL UNIQUE,

    PRIMARY KEY (tag_id, surface_form),

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS chunk_tags (
    chunk_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,

    PRIMARY KEY (chunk_id, tag_id),

    FOREIGN KEY (chunk_id)
        REFERENCES chunks(chunk_id) ON DELETE CASCADE,

    FOREIGN KEY (tag_id)
        REFERENCES tags(tag_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS records (
    record_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    equipment_tag TEXT,
    text_for_index TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    indexed_at TEXT,
    review_status TEXT NOT NULL DEFAULT 'UNREVIEWED',
    synthetic INTEGER NOT NULL DEFAULT 0
        CHECK (synthetic IN (0, 1)),
    source_class TEXT NOT NULL
        CHECK (source_class IN ('APPROVED_DOC', 'RECORD'))
);

CREATE INDEX IF NOT EXISTS idx_records_equipment_tag
    ON records(equipment_tag);

CREATE INDEX IF NOT EXISTS idx_records_kind
    ON records(kind);
"""


def connect_db(db_path=DEFAULT_DB_PATH):
    """Open a connection with foreign-key enforcement enabled."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db(db_path=DEFAULT_DB_PATH):
    """Initialize the schema; safe to call repeatedly."""
    path = Path(db_path)

    with connect_db(path) as connection:
        mode = connection.execute(
            "PRAGMA journal_mode = WAL"
        ).fetchone()[0]

        if mode.lower() != "wal":
            raise RuntimeError(
                f"Could not enable WAL mode: SQLite returned {mode!r}"
            )

        connection.executescript(SCHEMA)

    return path
