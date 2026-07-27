from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

import sqlite_vec
from sqlite_vec import serialize_float32

from app.config import DRAWING_DATABASE_PATH


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS drawings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL UNIQUE,
    drawing_number TEXT,
    title TEXT,
    revision TEXT,
    drawing_date TEXT,
    material TEXT,
    component_description TEXT,
    summary TEXT,
    analysis_json TEXT NOT NULL,
    source_path TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_drawings_document_id
    ON drawings(document_id);

CREATE INDEX IF NOT EXISTS idx_drawings_drawing_number
    ON drawings(drawing_number);

CREATE INDEX IF NOT EXISTS idx_drawings_title
    ON drawings(title);

CREATE TABLE IF NOT EXISTS drawing_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drawing_id INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_type TEXT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding_model TEXT,
    embedding_dimensions INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY(drawing_id)
        REFERENCES drawings(id)
        ON DELETE CASCADE,

    UNIQUE(drawing_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_drawing_chunks_drawing_id
    ON drawing_chunks(drawing_id);

CREATE INDEX IF NOT EXISTS idx_drawing_chunks_chunk_type
    ON drawing_chunks(chunk_type);

CREATE TABLE IF NOT EXISTS vector_index_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def get_database_path() -> Path:
    path = Path(DRAWING_DATABASE_PATH).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def open_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(
        get_database_path(),
        timeout=30,
    )

    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")

    connection.enable_load_extension(True)

    try:
        sqlite_vec.load(connection)
    finally:
        connection.enable_load_extension(False)

    return connection


@contextmanager
def database_connection() -> Iterator[sqlite3.Connection]:
    connection = open_connection()

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialise_database() -> Path:
    with database_connection() as connection:
        connection.executescript(SCHEMA_SQL)

    return get_database_path()


def get_sqlite_vec_version() -> str:
    with database_connection() as connection:
        row = connection.execute(
            "SELECT vec_version()"
        ).fetchone()

    if row is None:
        raise RuntimeError(
            "sqlite-vec loaded but returned no version."
        )

    return str(row[0])


def initialise_vector_index(
    dimensions: int,
    embedding_model: str,
) -> None:
    if dimensions <= 0:
        raise ValueError(
            "Embedding dimensions must be greater than zero."
        )

    if not embedding_model.strip():
        raise ValueError(
            "Embedding model cannot be empty."
        )

    now = utc_now()

    with database_connection() as connection:
        connection.executescript(SCHEMA_SQL)

        existing = connection.execute(
            """
            SELECT embedding_model, dimensions
            FROM vector_index_metadata
            WHERE id = 1
            """
        ).fetchone()

        if existing is not None:
            existing_model = str(existing["embedding_model"])
            existing_dimensions = int(existing["dimensions"])

            if existing_dimensions != dimensions:
                raise RuntimeError(
                    "The vector index already exists with "
                    f"{existing_dimensions} dimensions, but the new "
                    f"embedding has {dimensions} dimensions."
                )

            if existing_model != embedding_model:
                raise RuntimeError(
                    "The vector index already exists for model "
                    f"'{existing_model}', but '{embedding_model}' "
                    "was requested."
                )

        connection.execute(
            f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS drawing_chunk_vectors
            USING vec0(
                chunk_id INTEGER PRIMARY KEY,
                embedding FLOAT[{dimensions}]
            )
            """
        )

        connection.execute(
            """
            INSERT INTO vector_index_metadata (
                id,
                embedding_model,
                dimensions,
                created_at,
                updated_at
            )
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (
                embedding_model,
                dimensions,
                now,
                now,
            ),
        )


def store_vector(
    chunk_id: int,
    embedding: list[float],
) -> None:
    if chunk_id <= 0:
        raise ValueError(
            "chunk_id must be greater than zero."
        )

    if not embedding:
        raise ValueError(
            "Embedding cannot be empty."
        )

    vector_blob = serialize_float32(embedding)

    with database_connection() as connection:
        metadata = connection.execute(
            """
            SELECT dimensions
            FROM vector_index_metadata
            WHERE id = 1
            """
        ).fetchone()

        if metadata is None:
            raise RuntimeError(
                "Vector index has not been initialised."
            )

        expected_dimensions = int(metadata["dimensions"])

        if len(embedding) != expected_dimensions:
            raise ValueError(
                f"Expected an embedding with "
                f"{expected_dimensions} dimensions, received "
                f"{len(embedding)}."
            )

        connection.execute(
            """
            INSERT OR REPLACE INTO drawing_chunk_vectors (
                chunk_id,
                embedding
            )
            VALUES (?, ?)
            """,
            (
                chunk_id,
                vector_blob,
            ),
        )
