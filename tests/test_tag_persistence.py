
import sqlite3
from pathlib import Path

from noesis.ingest.pipeline import ingest_pdf

PDF_PATH = Path(
    "corpus/synthetic/Synthetic_Centrifugal_Pump_Manual.pdf"
)


def fetch_all(db_path, query, parameters=()):
    connection = sqlite3.connect(db_path)
    try:
        return connection.execute(query, parameters).fetchall()
    finally:
        connection.close()


def test_canonical_tag_and_aliases_are_persisted(tmp_path):
    db_path = tmp_path / "noesis.db"
    ingest_pdf(PDF_PATH, db_path=db_path)

    tags = fetch_all(
        db_path,
        "SELECT tag_id FROM tags WHERE canonical = ?",
        ("P101A",),
    )
    assert len(tags) == 1

    aliases = {
        row[0]
        for row in fetch_all(
            db_path,
            """
            SELECT surface_form
            FROM tag_aliases
            WHERE tag_id = ?
            """,
            (tags[0][0],),
        )
    }

    assert {"P-101A", "P 101 A", "p101a"} <= aliases


def test_tag_is_linked_to_chunks_that_mention_it(tmp_path):
    db_path = tmp_path / "noesis.db"
    ingest_pdf(PDF_PATH, db_path=db_path)

    rows = fetch_all(
        db_path,
        """
        SELECT DISTINCT c.chunk_id, c.text
        FROM chunks AS c
        JOIN chunk_tags AS ct ON ct.chunk_id = c.chunk_id
        JOIN tags AS t ON t.tag_id = ct.tag_id
        WHERE t.canonical = ?
        """,
        ("P101A",),
    )

    assert rows
    for chunk_id, text in rows:
     assert all(
    any(
        form in text
        for form in ("P-101A", "P 101 A", "p101a", "P101A")
    )
    for _, text in rows
)


def test_reingestion_does_not_duplicate_tags_or_aliases(tmp_path):
    db_path = tmp_path / "noesis.db"

    ingest_pdf(PDF_PATH, db_path=db_path, parse_version="1")

    first_counts = fetch_all(
        db_path,
        """
        SELECT
            (SELECT COUNT(*) FROM tags WHERE canonical = 'P101A'),
            (SELECT COUNT(*)
             FROM tag_aliases
             WHERE surface_form IN ('P-101A', 'P 101 A', 'p101a')),
            (SELECT COUNT(*)
             FROM chunk_tags AS ct
             JOIN tags AS t ON t.tag_id = ct.tag_id
             WHERE t.canonical = 'P101A')
        """,
    )[0]

    result = ingest_pdf(
        PDF_PATH, db_path=db_path, parse_version="2"
    )
    assert result["status"] == "reingested"

    second_counts = fetch_all(
        db_path,
        """
        SELECT
            (SELECT COUNT(*) FROM tags WHERE canonical = 'P101A'),
            (SELECT COUNT(*)
             FROM tag_aliases
             WHERE surface_form IN ('P-101A', 'P 101 A', 'p101a')),
            (SELECT COUNT(*)
             FROM chunk_tags AS ct
             JOIN tags AS t ON t.tag_id = ct.tag_id
             WHERE t.canonical = 'P101A')
        """,
    )[0]

    assert first_counts[:2] == second_counts[:2]
    assert second_counts[2] > 0
