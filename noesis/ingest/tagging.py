
"""Discover equipment tags in chunks and persist their relationships."""

import re
import sqlite3
from collections import defaultdict

from noesis.ingest.chunking import Chunk
from noesis.normalize import normalize_tag


# Match likely equipment-tag spellings, then let normalize_tag validate them.
CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:P|M|FIC|PI|TI|V)"
    r"(?:[\s_-]*\d{3})"
    r"(?:[\s_-]*[A-Za-z])?"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)


def discover_chunk_tags(chunks: list[Chunk]) -> dict[str, set[str]]:
    """Return canonical tags and observed aliases for each chunk key."""
    discovered: dict[str, set[str]] = defaultdict(set)

    for chunk in chunks:
        searchable_text = chunk["text"]

        for match in CANDIDATE_PATTERN.finditer(searchable_text):
            surface_form = match.group(0)
            canonical = normalize_tag(surface_form)

            if canonical is not None:
                discovered[chunk["chunk_key"]].add(canonical)

    return dict(discovered)


def persist_chunk_tags(
    connection: sqlite3.Connection,
    chunks: list[Chunk],
    chunk_ids: dict[str, int],
) -> int:
    """Persist canonical tags, observed aliases, and chunk links.

    The caller owns the transaction. Returns the number of unique
    chunk-to-tag relationships inserted.
    """
    relationships = discover_chunk_tags(chunks)
   
    aliases_by_tag: dict[str, set[str]] = defaultdict(set)

    for chunk in chunks:
        for match in CANDIDATE_PATTERN.finditer(chunk["text"]):
            surface = match.group(0)
            canonical = normalize_tag(surface)

            if canonical is not None:
                aliases_by_tag[canonical].add(surface)

    tag_ids: dict[str, int] = {}

    for canonical in sorted(aliases_by_tag):
        connection.execute(
            """
            INSERT INTO tags (canonical)
            VALUES (?)
            ON CONFLICT(canonical) DO NOTHING
            """,
            (canonical,),
        )

        row = connection.execute(
            "SELECT tag_id FROM tags WHERE canonical = ?",
            (canonical,),
        ).fetchone()
        tag_ids[canonical] = int(row["tag_id"])

        for surface in sorted(aliases_by_tag[canonical]):
            # A surface form can map to only one tag under the schema's
            # UNIQUE constraint. Do not overwrite an existing mapping.
            existing = connection.execute(
                """
                SELECT tag_id FROM tag_aliases WHERE surface_form = ?
                """,
                (surface,),
            ).fetchone()

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO tag_aliases (tag_id, surface_form)
                    VALUES (?, ?)
                    """,
                    (tag_ids[canonical], surface),
                )
            elif int(existing["tag_id"]) != tag_ids[canonical]:
                raise ValueError(
                    f"Alias {surface!r} is already assigned to another tag"
                )

    inserted = 0

    for chunk_key, canonicals in relationships.items():
        if chunk_key not in chunk_ids:
            raise ValueError(f"Missing database ID for {chunk_key!r}")

        for canonical in sorted(canonicals):
            cursor = connection.execute(
                """
                INSERT INTO chunk_tags (chunk_id, tag_id)
                VALUES (?, ?)
                ON CONFLICT(chunk_id, tag_id) DO NOTHING
                """,
                (chunk_ids[chunk_key], tag_ids[canonical]),
            )
            inserted += cursor.rowcount

    return inserted
