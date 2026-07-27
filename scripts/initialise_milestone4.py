from app.storage.vector_store import (
    get_database_path,
    get_sqlite_vec_version,
    initialise_database,
)


def main() -> None:
    database_path = initialise_database()
    vector_version = get_sqlite_vec_version()

    print("Milestone 4 database initialised successfully.")
    print(f"Database: {database_path}")
    print(f"sqlite-vec: {vector_version}")


if __name__ == "__main__":
    main()
