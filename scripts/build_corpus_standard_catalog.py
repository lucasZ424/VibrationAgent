"""Build the standard scope catalog from Qdrant document identity metadata."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import load  # noqa: E402
from vibration_agent.retrieval.query_normalize import standard_identifiers_from_sources  # noqa: E402
from vibration_agent.storage.qdrant_client import create_client, scroll_payloads  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "taxonomy" / "corpus_standards.yaml")
    args = parser.parse_args(argv)
    settings = load(ROOT)
    if not settings.database.qdrant_enabled:
        raise RuntimeError("Corpus standard catalog generation requires Qdrant.")
    client = create_client(
        url=settings.database.qdrant_url,
        api_key=settings.database.qdrant_api_key,
        timeout=settings.database.qdrant_timeout,
    )
    rows = scroll_payloads(client, collection=settings.database.qdrant_collection)
    identifiers = standard_identifiers_from_sources(rows)
    if not identifiers:
        raise RuntimeError("No standard document identifiers found in Qdrant source metadata.")
    payload = {
        "schema_version": "phase5.corpus_standards.v1",
        "source": {
            "backend": "qdrant",
            "collection": settings.database.qdrant_collection,
            "generated_at": date.today().isoformat(),
            "identity_fields": ["source_title", "source_filename", "doc_id", "title"],
        },
        "identifiers": list(identifiers),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"catalog: {args.output}")
    print(f"identifiers: {len(identifiers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
