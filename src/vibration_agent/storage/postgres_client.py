"""Thin runtime adapter around the optional psycopg package.

Kept schema-agnostic (no import of ``storage.postgres``) so the dependency stays
one-way and there is no import cycle: ``postgres`` -> ``postgres_client``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ORDER_BY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\s+(?:ASC|DESC))?$", re.IGNORECASE)


class PostgresDependencyError(RuntimeError):
    """Raised when psycopg is required at runtime but is not installed."""


def _safe_identifier(name: str) -> str:
    """Guard interpolated SQL identifiers (values are always parameterized)."""
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def connect(url: str, *, connect_timeout: float = 5.0) -> Any:
    try:
        import psycopg  # type: ignore
    except ModuleNotFoundError as exc:
        raise PostgresDependencyError("psycopg is not installed.") from exc
    return psycopg.connect(url, connect_timeout=connect_timeout)


def apply_migrations(conn: Any, migrations_dir: str | Path) -> list[str]:
    """Apply every ``*.sql`` in ``migrations_dir`` once, in filename order.

    Idempotent / replayable: a ``schema_migrations`` table records applied files,
    so re-running skips them and never re-executes DDL.
    """
    directory = Path(migrations_dir)
    applied: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())"
        )
        conn.commit()
        cur.execute("SELECT filename FROM schema_migrations")
        done = {row[0] for row in cur.fetchall()}
        # Backfill: a DB whose base schema (001) was applied out-of-band has an
        # empty ledger; mark 001 applied so we do not re-run its bare CREATE TABLE.
        # Later migrations use IF NOT EXISTS and apply safely on top.
        if not done:
            cur.execute("SELECT to_regclass('qa_logs')")
            base_exists = cur.fetchone()[0] is not None
            if base_exists:
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s) ON CONFLICT DO NOTHING",
                    ("001_init.sql",),
                )
                conn.commit()
                done.add("001_init.sql")
        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            cur.execute(path.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
            conn.commit()
            applied.append(path.name)
    return applied


def insert_row(
    conn: Any,
    table: str,
    row: Mapping[str, Any],
    *,
    jsonb_columns: Sequence[str] = (),
) -> Any:
    """Insert one row and return its primary key.

    ``row`` must already be restricted to real columns of ``table`` (the caller
    owns column validation). ``jsonb_columns`` are serialized with json and cast
    to ``jsonb`` so this adapter needs no psycopg-specific type imports.
    """
    columns = list(row.keys())
    if not columns:
        raise ValueError("insert_row requires at least one column")
    _safe_identifier(table)
    jsonb = set(jsonb_columns)
    placeholders: list[str] = []
    values: list[Any] = []
    for column in columns:
        _safe_identifier(column)
        value = row[column]
        if column in jsonb:
            placeholders.append("%s::jsonb")
            values.append(None if value is None else json.dumps(value))
        else:
            placeholders.append("%s")
            values.append(value)
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({', '.join(placeholders)}) RETURNING id"
    )
    with conn.cursor() as cur:
        cur.execute(sql, values)
        new_id = cur.fetchone()[0]
    conn.commit()
    return new_id


def fetch_rows(conn: Any, table: str, *, limit: int = 50, order_by: str = "id DESC") -> list[dict[str, Any]]:
    """Read rows back as dicts (used by the roundtrip integration test)."""
    _safe_identifier(table)
    if not _ORDER_BY_RE.match(order_by):
        raise ValueError(f"Unsafe order_by clause: {order_by!r}")
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM {table} ORDER BY {order_by} LIMIT %s", (limit,))
        columns = [description[0] for description in cur.description]
        return [dict(zip(columns, record, strict=True)) for record in cur.fetchall()]
