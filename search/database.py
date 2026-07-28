import sqlite3
from pathlib import Path

from app.config import SEARCH_DATABASE_PATH


_DOCUMENT_COLUMNS: dict[str, str] = {
    "sheet_number": "TEXT",
    "scale": "TEXT",
    "part_number": "TEXT",
    "manufacturing_process": "TEXT",
    "engineering_standards": "TEXT",
    "referenced_parts": "TEXT",
    "components": "TEXT",
    "engineering_notes": "TEXT",
    "body": "TEXT",
}

_FTS_COLUMNS = (
    "drawing_id UNINDEXED",
    "filename",
    "drawing_number",
    "revision",
    "title",
    "material",
    "finish",
    "units",
    "part_numbers",
    "dimensions_text",
    "tolerances_text",
    "notes_text",
    "engineering_standards",
    "components",
    "body",
    "searchable_text",
)

_REQUIRED_FTS_NAMES = {
    "drawing_id",
    "filename",
    "drawing_number",
    "revision",
    "title",
    "material",
    "finish",
    "units",
    "part_numbers",
    "dimensions_text",
    "tolerances_text",
    "notes_text",
    "engineering_standards",
    "components",
    "body",
    "searchable_text",
}


class SearchDatabase:
    def __init__(self, db_path: str | None = None):
        self.db_path = Path(db_path or SEARCH_DATABASE_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def initialize(self) -> None:
        cursor = self.conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS drawing_search_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drawing_id TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,

                drawing_number TEXT,
                revision TEXT,
                title TEXT,
                material TEXT,
                finish TEXT,
                units TEXT,

                sheet_number TEXT,
                scale TEXT,
                part_number TEXT,

                part_numbers TEXT,
                dimensions_text TEXT,
                tolerances_text TEXT,
                notes_text TEXT,

                manufacturing_process TEXT,
                engineering_standards TEXT,
                referenced_parts TEXT,
                components TEXT,
                engineering_notes TEXT,
                body TEXT,

                searchable_text TEXT NOT NULL,

                analysis_version TEXT,

                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        self._ensure_document_columns(cursor)
        self._ensure_fts(cursor)
        self.conn.commit()

    def _ensure_document_columns(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute("PRAGMA table_info(drawing_search_documents)")
        existing = {row[1] for row in cursor.fetchall()}

        for column_name, column_type in _DOCUMENT_COLUMNS.items():
            if column_name in existing:
                continue

            cursor.execute(
                f"ALTER TABLE drawing_search_documents "
                f"ADD COLUMN {column_name} {column_type}"
            )

    def _fts_column_names(self, cursor: sqlite3.Cursor) -> set[str]:
        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'drawing_search_fts'
            """
        )

        if cursor.fetchone() is None:
            return set()

        cursor.execute("PRAGMA table_info(drawing_search_fts)")
        return {row[1] for row in cursor.fetchall()}

    def _create_fts(self, cursor: sqlite3.Cursor) -> None:
        columns = ",\n                ".join(_FTS_COLUMNS)
        cursor.execute(
            f"""
            CREATE VIRTUAL TABLE drawing_search_fts
            USING fts5(
                {columns}
            )
            """
        )

    def _rebuild_fts_from_documents(self, cursor: sqlite3.Cursor) -> None:
        cursor.execute(
            """
            INSERT INTO drawing_search_fts (
                drawing_id,
                filename,
                drawing_number,
                revision,
                title,
                material,
                finish,
                units,
                part_numbers,
                dimensions_text,
                tolerances_text,
                notes_text,
                engineering_standards,
                components,
                body,
                searchable_text
            )
            SELECT
                drawing_id,
                filename,
                COALESCE(drawing_number, ''),
                COALESCE(revision, ''),
                COALESCE(title, ''),
                COALESCE(material, ''),
                COALESCE(finish, ''),
                COALESCE(units, ''),
                COALESCE(part_numbers, ''),
                COALESCE(dimensions_text, ''),
                COALESCE(tolerances_text, ''),
                COALESCE(notes_text, ''),
                COALESCE(engineering_standards, ''),
                COALESCE(components, ''),
                COALESCE(body, ''),
                searchable_text
            FROM drawing_search_documents
            """
        )

    def _ensure_fts(self, cursor: sqlite3.Cursor) -> None:
        existing = self._fts_column_names(cursor)

        if not existing:
            self._create_fts(cursor)
            return

        if _REQUIRED_FTS_NAMES.issubset(existing):
            return

        cursor.execute("DROP TABLE drawing_search_fts")
        self._create_fts(cursor)
        self._rebuild_fts_from_documents(cursor)

    def rebuild_fts(self, force: bool = True) -> dict[str, int | bool]:
        """Rebuild the FTS virtual table from drawing_search_documents."""
        cursor = self.conn.cursor()
        self._ensure_document_columns(cursor)

        existing = self._fts_column_names(cursor)
        rebuilt = False

        if force or not _REQUIRED_FTS_NAMES.issubset(existing):
            if existing:
                cursor.execute("DROP TABLE drawing_search_fts")
            self._create_fts(cursor)
            self._rebuild_fts_from_documents(cursor)
            rebuilt = True
        elif not existing:
            self._create_fts(cursor)
            self._rebuild_fts_from_documents(cursor)
            rebuilt = True

        self.conn.commit()

        cursor.execute("SELECT COUNT(*) FROM drawing_search_documents")
        document_count = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM drawing_search_fts")
        fts_count = int(cursor.fetchone()[0])

        return {
            "rebuilt": rebuilt,
            "document_count": document_count,
            "fts_count": fts_count,
        }

    def validate_fts_integrity(self) -> dict[str, object]:
        """Validate document vs FTS counts and required FTS columns."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM drawing_search_documents")
        document_count = int(cursor.fetchone()[0])

        fts_columns = self._fts_column_names(cursor)
        fts_exists = bool(fts_columns)
        fts_count = 0

        if fts_exists:
            cursor.execute("SELECT COUNT(*) FROM drawing_search_fts")
            fts_count = int(cursor.fetchone()[0])

        missing_columns = sorted(_REQUIRED_FTS_NAMES - fts_columns)
        counts_match = fts_exists and document_count == fts_count

        return {
            "fts_exists": fts_exists,
            "document_count": document_count,
            "fts_count": fts_count,
            "counts_match": counts_match,
            "missing_fts_columns": missing_columns,
            "ok": counts_match and not missing_columns,
        }

    def close(self) -> None:
        self.conn.close()
