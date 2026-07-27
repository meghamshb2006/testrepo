from app.storage.vector_store import (
    database_connection,
    initialise_database,
    initialise_vector_index,
    store_vector,
    utc_now,
)


def main() -> None:
    initialise_database()

    test_model = "milestone4-smoke-test"
    test_dimensions = 4

    initialise_vector_index(
        dimensions=test_dimensions,
        embedding_model=test_model,
    )

    now = utc_now()

    with database_connection() as connection:
        connection.execute(
            """
            INSERT INTO drawings (
                document_id,
                drawing_number,
                title,
                analysis_json,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (
                "milestone4-smoke-document",
                "TEST-001",
                "Milestone 4 Smoke Drawing",
                "{}",
                now,
                now,
            ),
        )

        drawing = connection.execute(
            """
            SELECT id
            FROM drawings
            WHERE document_id = ?
            """,
            ("milestone4-smoke-document",),
        ).fetchone()

        if drawing is None:
            raise RuntimeError(
                "Failed to create smoke-test drawing."
            )

        drawing_id = int(drawing["id"])

        connection.execute(
            """
            INSERT INTO drawing_chunks (
                drawing_id,
                chunk_index,
                chunk_type,
                chunk_text,
                embedding_model,
                embedding_dimensions,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drawing_id, chunk_index) DO UPDATE SET
                chunk_text = excluded.chunk_text,
                updated_at = excluded.updated_at
            """,
            (
                drawing_id,
                0,
                "summary",
                "Mechanical housing with snap features.",
                test_model,
                test_dimensions,
                now,
                now,
            ),
        )

        chunk = connection.execute(
            """
            SELECT id
            FROM drawing_chunks
            WHERE drawing_id = ?
              AND chunk_index = 0
            """,
            (drawing_id,),
        ).fetchone()

        if chunk is None:
            raise RuntimeError(
                "Failed to create smoke-test chunk."
            )

        chunk_id = int(chunk["id"])

    store_vector(
        chunk_id=chunk_id,
        embedding=[0.10, 0.20, 0.30, 0.40],
    )

    with database_connection() as connection:
        result = connection.execute(
            """
            SELECT
                chunk_id,
                distance
            FROM drawing_chunk_vectors
            WHERE embedding MATCH ?
              AND k = 1
            ORDER BY distance
            """,
            ("[0.10, 0.20, 0.30, 0.40]",),
        ).fetchone()

    if result is None:
        raise RuntimeError(
            "Vector search returned no result."
        )

    print("Milestone 4 vector smoke test passed.")
    print(f"Matched chunk ID: {result['chunk_id']}")
    print(f"Distance: {result['distance']}")


if __name__ == "__main__":
    main()
