"""Persist existing ingestion exports to configured runtime stores."""
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
from vibration_agent.storage.ingestion import persist_ingestion_result  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _chunks_path(settings: Settings, source_type: str, doc_id: str, manifest: dict[str, Any]) -> Path:
    output = manifest.get("outputs", {}).get("chunks_jsonl") if isinstance(manifest.get("outputs"), dict) else None
    if output:
        return Path(output)
    return settings.paths.chunks_dir / source_type / doc_id / "chunks.jsonl"


def load_export_documents(settings: Settings, *, source_type: str, doc_id: str | None = None) -> list[dict[str, Any]]:
    root = settings.paths.exports_dir / source_type
    if doc_id:
        manifest_paths = [root / doc_id / "manifest.json"]
    else:
        manifest_paths = sorted(root.glob("*/manifest.json"))

    documents: list[dict[str, Any]] = []
    for manifest_path in manifest_paths:
        if not manifest_path.exists():
            continue
        manifest = _read_json(manifest_path)
        resolved_doc_id = str(manifest.get("doc_id") or manifest_path.parent.name)
        chunks_path = _chunks_path(settings, source_type, resolved_doc_id, manifest)
        if not chunks_path.exists():
            documents.append({"manifest": manifest, "chunks": [], "warnings": [f"Missing chunks file: {chunks_path}"]})
            continue
        documents.append({"manifest": manifest, "chunks": _read_jsonl(chunks_path)})
    return documents


def _write_json(payload: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Persist existing ingestion exports to Postgres/Qdrant.")
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--source-type", required=True)
    parser.add_argument("--doc-id", default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        settings = load(args.workspace)
        documents = load_export_documents(settings, source_type=args.source_type, doc_id=args.doc_id)
        result = {
            "status": "ok" if documents else "insufficient",
            "source_type": args.source_type,
            "doc_id": args.doc_id,
            "document_count": len(documents),
            "documents": documents,
            "warnings": [
                warning
                for document in documents
                for warning in document.get("warnings", [])
                if isinstance(warning, str)
            ],
        }
        result["storage"] = persist_ingestion_result(result, settings=settings)
        result["warnings"].extend(result["storage"].get("warnings", []))
        _write_json(result, args.output)
        return 0 if result["status"] == "ok" else 2
    except Exception as exc:
        _write_json(
            {"status": "fail", "error_type": type(exc).__name__, "error": str(exc)},
            args.output,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
