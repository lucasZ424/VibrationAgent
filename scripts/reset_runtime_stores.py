"""Reset runtime ingestion stores to a clean local baseline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.storage import postgres_client, qdrant  # noqa: E402

_INGESTION_TABLES = ("citations", "figures_tables", "chunks", "document_sections", "documents")


def postgres_reset_sql() -> str:
    return f"TRUNCATE {', '.join(_INGESTION_TABLES)} RESTART IDENTITY CASCADE"


def _reset_postgres(settings: Settings, *, execute: bool) -> dict[str, Any]:
    if not settings.database.postgres_enabled:
        return {"status": "disabled", "tables": list(_INGESTION_TABLES)}
    if not settings.database.postgres_url:
        return {"status": "fail", "error": "POSTGRES_ENABLED is true but POSTGRES_URL is empty."}
    if not execute:
        return {"status": "dry_run", "tables": list(_INGESTION_TABLES), "sql": postgres_reset_sql()}

    conn = postgres_client.connect(settings.database.postgres_url, connect_timeout=settings.database.postgres_timeout)
    try:
        with conn.cursor() as cur:
            cur.execute(postgres_reset_sql())
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"status": "reset", "tables": list(_INGESTION_TABLES)}


def _collection_exists(client: Any, collection: str) -> bool:
    if hasattr(client, "collection_exists"):
        return bool(client.collection_exists(collection))
    try:
        client.get_collection(collection)
        return True
    except Exception:
        return False


def _reset_qdrant(settings: Settings, *, execute: bool) -> dict[str, Any]:
    if not settings.database.qdrant_enabled:
        return {"status": "disabled", "collection": settings.database.qdrant_collection}
    collection = settings.database.qdrant_collection
    if not execute:
        return {"status": "dry_run", "collection": collection, "action": "delete_collection_if_exists"}

    client = qdrant.runtime_client(settings)
    existed = _collection_exists(client, collection)
    if existed:
        client.delete_collection(collection)
    return {"status": "reset", "collection": collection, "existed": existed}


def _write_json(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset local Postgres/Qdrant ingestion stores.")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--execute", action="store_true", help="Actually reset stores. Omit for dry run.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        settings = load(args.workspace)
        result = {
            "status": "reset" if args.execute else "dry_run",
            "execute": args.execute,
            "postgres": _reset_postgres(settings, execute=args.execute),
            "qdrant": _reset_qdrant(settings, execute=args.execute),
        }
        _write_json(result, args.output)
        return 0
    except Exception as exc:
        _write_json({"status": "fail", "error_type": type(exc).__name__, "error": str(exc)}, args.output)
        return 1


if __name__ == "__main__":
    sys.exit(main())
