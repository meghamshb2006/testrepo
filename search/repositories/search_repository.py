import re
from typing import Any

from search.database import SearchDatabase
from search.models.search_document import SearchDocument


_FTS_OPERATOR_PATTERN = re.compile(r"^\s*(AND|OR|NOT)\s*$", re.IGNORECASE)

_DOCUMENT_COLUMNS = (
    "drawing_id",
    "filename",
    "drawing_number",
    "revision",
    "title",
    "material",
    "finish",
    "units",
    "sheet_number",
    "scale",
    "part_number",
    "part_numbers",
    "dimensions_text",
    "tolerances_text",
    "notes_text",
    "manufacturing_process",
    "engineering_standards",
    "referenced_parts",
    "components",
    "engineering_notes",
    "body",
    "searchable_text",
    "analysis_version",
    "created_at",
    "updated_at",
)

_FTS_INSERT_COLUMNS = (
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
)


class SearchRepository:
    def __init__(self, database: SearchDatabase):
        self.database = database

    def upsert(self, document: SearchDocument) -> None:
        cursor = self.database.conn.cursor()
        placeholders = ", ".join("?" for _ in _DOCUMENT_COLUMNS)
        column_list = ", ".join(_DOCUMENT_COLUMNS)
        update_assignments = ",\n                ".join(
            f"{column} = excluded.{column}"
            for column in _DOCUMENT_COLUMNS
            if column != "drawing_id"
        )

        values = (
            document.drawing_id,
            document.filename,
            document.drawing_number,
            document.revision,
            document.title,
            document.material,
            document.finish,
            document.units,
            document.sheet_number,
            document.scale,
            document.part_number,
            document.part_numbers,
            document.dimensions_text,
            document.tolerances_text,
            document.notes_text,
            document.manufacturing_process,
            document.engineering_standards,
            document.referenced_parts,
            document.components,
            document.engineering_notes,
            document.body,
            document.searchable_text,
            document.analysis_version,
            document.created_at.isoformat(),
            document.updated_at.isoformat(),
        )

        cursor.execute(
            f"""
            INSERT INTO drawing_search_documents (
                {column_list}
            )
            VALUES ({placeholders})
            ON CONFLICT(drawing_id) DO UPDATE SET
                {update_assignments}
            """,
            values,
        )

        cursor.execute(
            "DELETE FROM drawing_search_fts WHERE drawing_id = ?",
            (document.drawing_id,),
        )

        fts_placeholders = ", ".join("?" for _ in _FTS_INSERT_COLUMNS)
        fts_column_list = ", ".join(_FTS_INSERT_COLUMNS)
        fts_values = (
            document.drawing_id,
            document.filename,
            document.drawing_number or "",
            document.revision or "",
            document.title or "",
            document.material or "",
            document.finish or "",
            document.units or "",
            document.part_numbers,
            document.dimensions_text,
            document.tolerances_text,
            document.notes_text,
            document.engineering_standards,
            document.components,
            document.body,
            document.searchable_text,
        )

        cursor.execute(
            f"""
            INSERT INTO drawing_search_fts (
                {fts_column_list}
            )
            VALUES ({fts_placeholders})
            """,
            fts_values,
        )

        self.database.conn.commit()

    def get_by_drawing_id(self, drawing_id: str) -> dict[str, Any] | None:
        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM drawing_search_documents
            WHERE drawing_id = ?
            """,
            (drawing_id,),
        )

        row = cursor.fetchone()

        return dict(row) if row else None

    def list_all(self) -> list[dict[str, Any]]:
        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM drawing_search_documents
            ORDER BY updated_at DESC
            """
        )

        return [dict(row) for row in cursor.fetchall()]

    def delete(self, drawing_id: str) -> bool:
        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            DELETE FROM drawing_search_documents
            WHERE drawing_id = ?
            """,
            (drawing_id,),
        )

        deleted = cursor.rowcount > 0

        cursor.execute(
            """
            DELETE FROM drawing_search_fts
            WHERE drawing_id = ?
            """,
            (drawing_id,),
        )

        self.database.conn.commit()

        return deleted

    def count(self) -> int:
        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM drawing_search_documents
            """
        )

        return int(cursor.fetchone()[0])

    @staticmethod
    def _prepare_fts_query(query: str) -> str:
        prepared_tokens: list[str] = []

        for raw_token in query.split():
            token = raw_token.strip("?.!,;:\"'()[]{}")

            if not token:
                continue

            if _FTS_OPERATOR_PATTERN.match(token):
                prepared_tokens.append(token.upper())
                continue

            if token.startswith('"') and token.endswith('"'):
                prepared_tokens.append(token)
                continue

            if any(character in token for character in "-_/+."):
                prepared_tokens.append(f'"{token}"')
                continue

            prepared_tokens.append(token)

        return " ".join(prepared_tokens)

    def search_fts(
        self,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not isinstance(query, str):
            raise TypeError("query must be a string.")

        if not query.strip():
            raise ValueError("query must not be blank.")

        if not isinstance(limit, int):
            raise TypeError("limit must be an integer.")

        if limit < 1:
            raise ValueError("limit must be at least 1.")

        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            SELECT
                d.*,
                bm25(drawing_search_fts) AS fts_score
            FROM drawing_search_fts
            JOIN drawing_search_documents AS d
                ON d.drawing_id = drawing_search_fts.drawing_id
            WHERE drawing_search_fts MATCH ?
            ORDER BY fts_score ASC
            LIMIT ?
            """,
            (self._prepare_fts_query(query), limit),
        )

        return [dict(row) for row in cursor.fetchall()]
