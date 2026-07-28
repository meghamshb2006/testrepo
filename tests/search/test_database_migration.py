from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from search.database import SearchDatabase
from search.models.search_document import SearchDocument
from search.repositories.search_repository import SearchRepository


def test_additive_migration_adds_columns_and_rebuilds_fts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE drawing_search_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawing_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,
            drawing_number TEXT,
            revision TEXT,
            title TEXT,
            material TEXT,
            finish TEXT,
            units TEXT,
            part_numbers TEXT,
            dimensions_text TEXT,
            tolerances_text TEXT,
            notes_text TEXT,
            searchable_text TEXT NOT NULL,
            analysis_version TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE drawing_search_fts
        USING fts5(
            drawing_id UNINDEXED,
            filename,
            drawing_number,
            title,
            material,
            finish,
            units,
            part_numbers,
            dimensions_text,
            tolerances_text,
            notes_text,
            searchable_text
        )
        """
    )
    conn.execute(
        """
        INSERT INTO drawing_search_documents (
            drawing_id, filename, drawing_number, revision,
            searchable_text, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "drawing-001",
            "legacy.pdf",
            "DR-1023",
            "C",
            "DR-1023 revision C aluminium",
            "2024-01-01T00:00:00+00:00",
            "2024-01-01T00:00:00+00:00",
        ),
    )
    conn.execute(
        """
        INSERT INTO drawing_search_fts (
            drawing_id, filename, drawing_number, title, material,
            finish, units, part_numbers, dimensions_text,
            tolerances_text, notes_text, searchable_text
        )
        VALUES (?, ?, ?, '', '', '', '', '', '', '', '', ?)
        """,
        (
            "drawing-001",
            "legacy.pdf",
            "DR-1023",
            "DR-1023 revision C aluminium",
        ),
    )
    conn.commit()
    conn.close()

    database = SearchDatabase(str(db_path))
    database.initialize()

    cursor = database.conn.cursor()
    cursor.execute("PRAGMA table_info(drawing_search_documents)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "engineering_standards" in columns
    assert "body" in columns
    assert "components" in columns

    cursor.execute("PRAGMA table_info(drawing_search_fts)")
    fts_columns = {row[1] for row in cursor.fetchall()}
    assert "revision" in fts_columns
    assert "engineering_standards" in fts_columns
    assert "components" in fts_columns
    assert "body" in fts_columns

    repository = SearchRepository(database)
    results = repository.search_fts("DR-1023")
    assert len(results) == 1
    assert results[0]["drawing_id"] == "drawing-001"

    now = datetime.now(timezone.utc)
    repository.upsert(
        SearchDocument(
            drawing_id="drawing-002",
            filename="new.pdf",
            drawing_number="DR-2048",
            revision="A",
            engineering_standards="ISO-2768",
            components="housing",
            body="motor housing summary",
            searchable_text="DR-2048 ISO-2768 motor housing",
            created_at=now,
            updated_at=now,
        )
    )
    standard_hits = repository.search_fts("ISO-2768")
    assert any(row["drawing_id"] == "drawing-002" for row in standard_hits)

    database.close()
