"""Command-line entry point for Noesis corpus ingestion."""

import argparse
import sqlite3
import sys
from pathlib import Path

from noesis.db import DEFAULT_DB_PATH, connect_db
from noesis.ingest.pipeline import ingest_pdf


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest PDF manuals into the Noesis SQLite database."
    )
    parser.add_argument(
        "corpus",
        type=Path,
        help="Directory containing PDF manuals (searched recursively).",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path (default: {DEFAULT_DB_PATH}).",
    )
    parser.add_argument(
        "--parse-version",
        default="1",
        help="Parser version used to determine whether re-ingestion is needed.",
    )
    return parser


def corpus_summary(
    connection: sqlite3.Connection,
    filenames: list[str],
) -> dict[str, int]:
    """Summarize persisted data for the discovered corpus files."""
    if not filenames:
        return {
            "pages": 0,
            "sections": 0,
            "tables": 0,
            "warnings": 0,
            "tags": 0,
        }

    placeholders = ",".join("?" for _ in filenames)
    parameters = tuple(filenames)

    pages = connection.execute(
        f"""
        SELECT COALESCE(SUM(pages), 0)
        FROM documents
        WHERE filename IN ({placeholders})
        """,
        parameters,
    ).fetchone()[0]

    sections = connection.execute(
        f"""
        SELECT COUNT(DISTINCT c.section_path)
        FROM chunks AS c
        JOIN documents AS d ON d.doc_id = c.doc_id
        WHERE d.filename IN ({placeholders})
          AND c.section_path IS NOT NULL
          AND TRIM(c.section_path) <> ''
        """,
        parameters,
    ).fetchone()[0]

    roles = connection.execute(
        f"""
        SELECT c.chunk_role, COUNT(*)
        FROM chunks AS c
        JOIN documents AS d ON d.doc_id = c.doc_id
        WHERE d.filename IN ({placeholders})
        GROUP BY c.chunk_role
        """,
        parameters,
    ).fetchall()

    role_counts = {row[0]: row[1] for row in roles}

    tags = connection.execute(
        f"""
        SELECT COUNT(DISTINCT t.tag_id)
        FROM tags AS t
        JOIN chunk_tags AS ct ON ct.tag_id = t.tag_id
        JOIN chunks AS c ON c.chunk_id = ct.chunk_id
        JOIN documents AS d ON d.doc_id = c.doc_id
        WHERE d.filename IN ({placeholders})
        """,
        parameters,
    ).fetchone()[0]

    return {
        "pages": pages,
        "sections": sections,
        "tables": role_counts.get("table", 0),
        "warnings": role_counts.get("warning", 0),
        "tags": tags,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.corpus.is_dir():
        parser.error(f"Corpus directory does not exist: {args.corpus}")

    pdf_paths = sorted(
        path for path in args.corpus.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )

    if not pdf_paths:
        print(f"No PDF files found in {args.corpus}")
        return 0

    # The current database schema identifies documents by filename.
    # Detect collisions rather than silently conflating two different PDFs.
    filenames = [path.name for path in pdf_paths]
    if len(filenames) != len(set(filenames)):
        parser.error(
            "Multiple PDFs share the same filename. "
            "The current schema requires unique document filenames."
        )

    print(f"Corpus: {args.corpus}")
    print(f"PDF files found: {len(pdf_paths)}")

    outcomes = {"ingested": 0, "reingested": 0, "skipped": 0}

    try:
        for path in pdf_paths:
            result = ingest_pdf(
                path,
                db_path=args.db,
                parse_version=args.parse_version,
            )
            status = result["status"]
            outcomes[status] = outcomes.get(status, 0) + 1

            print(
                f"[{status.upper()}] {path.name} "
                f"({result['pages']} pages)"
            )

        with connect_db(args.db) as connection:
            summary = corpus_summary(connection, filenames)

    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    print("\nCorpus summary")
    print("-" * 36)
    print(f"Pages parsed/stored:           {summary['pages']}")
    print(f"Distinct section paths:        {summary['sections']}")
    print(f"Tables extracted:              {summary['tables']}")
    print(f"Warnings extracted:            {summary['warnings']}")
    print(f"Distinct equipment tags:       {summary['tags']}")
    print()
    print(f"Newly ingested: {outcomes['ingested']}")
    print(f"Re-ingested:    {outcomes['reingested']}")
    print(f"Skipped:        {outcomes['skipped']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())