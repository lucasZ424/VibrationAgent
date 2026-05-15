"""Apply db/postgres/migrations/*.sql to POSTGRES_URL, then create Qdrant collections."""
from __future__ import annotations


def main() -> None:
    # TODO: run each .sql in order; then call qdrant client to create `chunks` collection
    raise NotImplementedError


if __name__ == "__main__":
    main()
