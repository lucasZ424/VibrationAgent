"""PostgreSQL connection and thin CRUD helpers.

Tables owned here: documents, document_sections, chunks, figures_tables,
terms, symbols, units, citations, qa_logs. Schema in db/postgres/migrations/.
"""
from __future__ import annotations


def connect(url: str):
    # TODO: sqlalchemy engine / psycopg pool
    raise NotImplementedError
