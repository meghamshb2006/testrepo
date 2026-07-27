from __future__ import annotations

from pathlib import Path

import pytest

from search.database import SearchDatabase


def test_initialize_and_close(tmp_path: Path) -> None:
    db_path = tmp_path / "drawing_search.db"
    database = SearchDatabase(str(db_path))

    try:
        database.initialize()

        cursor = database.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {row[0] for row in cursor.fetchall()}

        assert "drawing_search_documents" in table_names
        assert "drawing_search_fts" in table_names

    finally:
        database.close()
