import sqlite3
from pathlib import Path


class SearchDatabase:
    def __init__(self, db_path: str = "data/drawing_search.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def initialize(self):
        cursor = self.conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS drawing_search_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drawing_id TEXT NOT NULL UNIQUE,
            filename TEXT NOT NULL,

            drawing_number TEXT,
            revision TEXT,
            title TEXT,
            material TEXT,

            part_numbers TEXT,
            dimensions_text TEXT,
            tolerances_text TEXT,
            notes_text TEXT,

            searchable_text TEXT NOT NULL,

            analysis_version TEXT,

            created_at TEXT,
            updated_at TEXT
        )
        """)

        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS drawing_search_fts
        USING fts5(
            drawing_id UNINDEXED,
            filename,
            drawing_number,
            title,
            material,
            part_numbers,
            dimensions_text,
            tolerances_text,
            notes_text,
            searchable_text
        )
        """)

        self.conn.commit()

    def close(self):
        self.conn.close()
