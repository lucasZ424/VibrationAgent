"""Phase-5 Obj3 reproducible PostgreSQL-to-Qdrant reindex CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import load  # noqa: E402
from vibration_agent.storage import postgres_client, qdrant  # noqa: E402
from vibration_agent.storage.reindex import load_postgres_chunks, run_reindex  # noqa: E402


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Write vectors; otherwise perform a dry run.")
    parser.add_argument("--batch-size", type=_positive_int)
    parser.add_argument("--timeout", type=_positive_float)
    parser.add_argument("--checkpoint", type=Path, default=Path("run_logs/obj3_reindex_checkpoint.json"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--recreate-collection", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load()
    if not settings.database.postgres_enabled or not settings.database.postgres_url:
        raise RuntimeError("Obj3 reindex requires enabled Postgres with POSTGRES_URL.")
    if args.batch_size is not None:
        settings.embeddings.batch_size = args.batch_size
    if args.timeout is not None:
        settings.embeddings.timeout = args.timeout
        settings.database.qdrant_timeout = args.timeout
    conn = postgres_client.connect(settings.database.postgres_url, connect_timeout=settings.database.postgres_timeout)
    try:
        chunks = load_postgres_chunks(conn)
    finally:
        conn.close()
    client = qdrant.runtime_client(settings)
    report = run_reindex(
        chunks,
        client=client,
        settings=settings,
        execute=args.execute,
        checkpoint_path=args.checkpoint,
        recreate_collection=args.recreate_collection,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["status"] in {"dry_run", "complete"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
