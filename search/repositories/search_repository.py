import re
from typing import Any

from search.database import SearchDatabase
from search.models.search_document import SearchDocument


_FTS_OPERATOR_PATTERN = re.compile(r"^\s*(AND|OR|NOT)\s*$", re.IGNORECASE)


class SearchRepository:
    def __init__(self, database: SearchDatabase):
        self.database = database

    def upsert(self, document: SearchDocument) -> None:
        cursor = self.database.conn.cursor()

        cursor.execute(
            """
            INSERT INTO drawing_search_documents (
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
                searchable_text,
                analysis_version,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drawing_id) DO UPDATE SET
                filename = excluded.filename,
                drawing_number = excluded.drawing_number,
                revision = excluded.revision,
                title = excluded.title,
                material = excluded.material,
                finish = excluded.finish,
                units = excluded.units,
                part_numbers = excluded.part_numbers,
                dimensions_text = excluded.dimensions_text,
                tolerances_text = excluded.tolerances_text,
                notes_text = excluded.notes_text,
                searchable_text = excluded.searchable_text,
                analysis_version = excluded.analysis_version,
                updated_at = excluded.updated_at
            """,
            (
                document.drawing_id,
                document.filename,
                document.drawing_number,
                document.revision,
                document.title,
                document.material,
                document.finish,
                document.units,
                document.part_numbers,
                document.dimensions_text,
                document.tolerances_text,
                document.notes_text,
                document.searchable_text,
                document.analysis_version,
                document.created_at.isoformat(),
                document.updated_at.isoformat(),
            ),
        )

        cursor.execute(
            "DELETE FROM drawing_search_fts WHERE drawing_id = ?",
            (document.drawing_id,),
        )

        cursor.execute(
            """
            INSERT INTO drawing_search_fts (
                drawing_id,
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document.drawing_id,
                document.filename,
                document.drawing_number or "",
                document.title or "",
                document.material or "",
                document.finish or "",
                document.units or "",
                document.part_numbers,
                document.dimensions_text,
                document.tolerances_text,
                document.notes_text,
                document.searchable_text,
            ),
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
