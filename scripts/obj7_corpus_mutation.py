"""Plan or apply the Obj7B direct source-identity corpus mutation."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

DEFAULT_CHUNKS_DIR = ROOT / "data" / "chunks"
DEFAULT_EXPORTS_DIR = ROOT / "data" / "exports"
DEFAULT_OUTPUT = ROOT / "run_logs" / "obj7_corpus_mutation.json"
REPORT_SCHEMA = "phase5.obj7.corpus_mutation.report.v1"
GENERIC_DOCUMENT_RE = r"document[_-][a-z0-9]+"


def configure_stdout_utf8() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except Exception:
        return


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} contains a non-object JSONL row.")
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(dict(row), ensure_ascii=False, separators=(",", ":")) + "\n")
    temporary.replace(path)


def discover_chunk_paths(chunks_dir: Path) -> list[Path]:
    return sorted(chunks_dir.glob("*/*/chunks.jsonl"))


def run_obj7_corpus_mutation(
    *,
    chunks_dir: Path = DEFAULT_CHUNKS_DIR,
    exports_dir: Path = DEFAULT_EXPORTS_DIR,
    chunk_paths: Sequence[Path] = (),
    execute: bool = False,
    sample_limit: int = 10,
) -> dict[str, Any]:
    paths = list(chunk_paths) if chunk_paths else discover_chunk_paths(chunks_dir)
    documents: list[dict[str, Any]] = []
    before_chunks: list[dict[str, Any]] = []
    after_chunks: list[dict[str, Any]] = []
    warnings: list[str] = []
    changed_documents = 0
    changed_chunks = 0
    field_updates: Counter[str] = Counter()

    for chunks_path in paths:
        chunks = read_jsonl(chunks_path)
        manifest_path = _manifest_path_for_chunks(chunks_path, chunks_dir=chunks_dir, exports_dir=exports_dir)
        manifest: dict[str, Any] = {}
        doc_warnings: list[str] = []
        if manifest_path.exists():
            manifest = read_json(manifest_path)
        else:
            doc_warnings.append(f"Missing manifest: {_rel(manifest_path)}")
        desired = _desired_source_identity(manifest, chunks[0] if chunks else {})
        mutated, doc_field_updates = _backfill_chunks(chunks, desired)
        doc_changed_chunks = sum(1 for old, new in zip(chunks, mutated, strict=True) if old != new)
        if execute and doc_changed_chunks:
            write_jsonl(chunks_path, mutated)
        if doc_changed_chunks:
            changed_documents += 1
            changed_chunks += doc_changed_chunks
        field_updates.update(doc_field_updates)
        before_chunks.extend(chunks)
        after_chunks.extend(mutated)
        warnings.extend(doc_warnings)
        documents.append(
            {
                "source_type": _source_type_for_chunks(chunks_path, chunks_dir),
                "doc_id": manifest.get("doc_id") or chunks_path.parent.name,
                "chunks_path": _rel(chunks_path),
                "manifest_path": _rel(manifest_path),
                "chunk_count": len(chunks),
                "changed_chunk_count": doc_changed_chunks,
                "field_update_counts": dict(sorted(doc_field_updates.items())),
                "desired_identity": desired,
                "warnings": doc_warnings,
            }
        )

    return {
        "schema_version": REPORT_SCHEMA,
        "mode": "execute" if execute else "dry_run",
        "strategy": "backfill_direct_source_identity_v1",
        "chunks_dir": _rel(chunks_dir),
        "exports_dir": _rel(exports_dir),
        "document_count": len(documents),
        "chunk_count": len(before_chunks),
        "changed_document_count": changed_documents,
        "changed_chunk_count": changed_chunks,
        "field_update_counts": dict(sorted(field_updates.items())),
        "content_fingerprint_before": _fingerprint(before_chunks, ("chunk_id", "text")),
        "content_fingerprint_after": _fingerprint(after_chunks, ("chunk_id", "text")),
        "identity_fingerprint_before": _fingerprint(before_chunks, _identity_fingerprint_fields()),
        "identity_fingerprint_after": _fingerprint(after_chunks, _identity_fingerprint_fields()),
        "source_type_counts": dict(sorted(Counter(str(chunk.get("source_type") or "unknown") for chunk in after_chunks).items())),
        "direct_source_identity_after": _direct_identity_summary(after_chunks),
        "generic_identity": _generic_identity_summary(after_chunks, sample_limit=sample_limit),
        "runtime_rebuild_requirement": {
            "postgres_refresh_required": changed_chunks > 0,
            "qdrant_payload_refresh_required": changed_chunks > 0,
            "qdrant_collection_recreate_required": False,
            "reason": _runtime_rebuild_reason(changed_chunks),
        },
        "warnings": warnings,
        "documents": documents,
    }


def _manifest_path_for_chunks(chunks_path: Path, *, chunks_dir: Path, exports_dir: Path) -> Path:
    try:
        relative = chunks_path.resolve().relative_to(chunks_dir.resolve())
    except ValueError:
        return exports_dir / chunks_path.parent.parent.name / chunks_path.parent.name / "manifest.json"
    parts = relative.parts
    if len(parts) < 3:
        return exports_dir / chunks_path.parent.parent.name / chunks_path.parent.name / "manifest.json"
    return exports_dir / parts[0] / parts[1] / "manifest.json"


def _source_type_for_chunks(chunks_path: Path, chunks_dir: Path) -> str:
    try:
        return chunks_path.resolve().relative_to(chunks_dir.resolve()).parts[0]
    except (ValueError, IndexError):
        return chunks_path.parent.parent.name


def _desired_source_identity(manifest: Mapping[str, Any], sample_chunk: Mapping[str, Any]) -> dict[str, str]:
    input_info = manifest.get("input") if isinstance(manifest.get("input"), Mapping) else {}
    source_path = _first_text(input_info.get("source_path"), sample_chunk.get("source_path"))
    filename = _first_text(
        input_info.get("filename"),
        _basename(source_path),
        sample_chunk.get("source_filename"),
        sample_chunk.get("filename"),
    )
    title = _first_text(
        manifest.get("title"),
        sample_chunk.get("source_title"),
        sample_chunk.get("title"),
        _stem(filename),
        manifest.get("doc_id"),
        sample_chunk.get("doc_id"),
    )
    desired: dict[str, str] = {}
    if filename:
        desired["source_filename"] = filename
    if title:
        desired["source_title"] = title
    if source_path:
        desired["source_path"] = source_path
    return desired


def _backfill_chunks(
    chunks: Sequence[Mapping[str, Any]],
    desired: Mapping[str, str],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    updates: Counter[str] = Counter()
    mutated: list[dict[str, Any]] = []
    for chunk in chunks:
        row = dict(chunk)
        for field, value in desired.items():
            if value and row.get(field) != value:
                row[field] = value
                updates[field] += 1
        mutated.append(row)
    return mutated, updates


def _identity_fingerprint_fields() -> tuple[str, ...]:
    return ("chunk_id", "source_type", "source_filename", "source_title", "source_path", "title")


def _runtime_rebuild_reason(changed_chunks: int) -> str:
    if not changed_chunks:
        return "No source-identity file changes are pending; runtime rebuild is not required by this mutation."
    return (
        "Chunk ids and text are unchanged; payload identity changed. Use a fresh reindex checkpoint "
        "or persist the refreshed exports so Qdrant payloads receive source_filename/source_title."
    )


def _fingerprint(chunks: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> str:
    material = "\n".join(
        json.dumps({field: chunk.get(field) for field in fields}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for chunk in sorted(chunks, key=lambda item: str(item.get("chunk_id") or ""))
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _direct_identity_summary(chunks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(chunks)
    filename = sum(1 for chunk in chunks if _has_text(chunk.get("source_filename")))
    title = sum(1 for chunk in chunks if _has_text(chunk.get("source_title")))
    path = sum(1 for chunk in chunks if _has_text(chunk.get("source_path")))
    return {
        "source_filename_count": filename,
        "source_filename_rate": _rate(filename, total),
        "source_title_count": title,
        "source_title_rate": _rate(title, total),
        "source_path_count": path,
        "source_path_rate": _rate(path, total),
    }


def _generic_identity_summary(chunks: Sequence[Mapping[str, Any]], *, sample_limit: int) -> dict[str, Any]:
    import re

    pattern = re.compile(GENERIC_DOCUMENT_RE, re.IGNORECASE)
    samples: list[dict[str, Any]] = []
    count = 0
    for chunk in chunks:
        values = (
            chunk.get("doc_id"),
            chunk.get("chunk_id"),
            chunk.get("source_filename"),
            chunk.get("source_title"),
            chunk.get("source_path"),
            chunk.get("title"),
        )
        if any(pattern.search(str(value)) for value in values if value is not None):
            count += 1
            if len(samples) < sample_limit:
                samples.append(
                    {
                        "chunk_id": chunk.get("chunk_id"),
                        "doc_id": chunk.get("doc_id"),
                        "source_filename": chunk.get("source_filename"),
                        "source_title": chunk.get("source_title"),
                        "source_path": chunk.get("source_path"),
                    }
                )
    return {"remaining_count": count, "remaining_samples": samples}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if _has_text(value):
            return str(value).strip()
    return None


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _basename(value: Any) -> str | None:
    text = _first_text(value)
    if text is None:
        return None
    return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or None


def _stem(value: Any) -> str | None:
    name = _basename(value)
    if not name:
        return None
    return Path(name).stem or None


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--exports-dir", type=Path, default=DEFAULT_EXPORTS_DIR)
    parser.add_argument("--chunk-path", type=Path, action="append", default=[])
    parser.add_argument("--execute", action="store_true", help="Rewrite chunk JSONL files. Omit for dry run.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args(argv)

    report = run_obj7_corpus_mutation(
        chunks_dir=args.chunks_dir,
        exports_dir=args.exports_dir,
        chunk_paths=args.chunk_path,
        execute=args.execute,
        sample_limit=args.sample_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "document_count": report["document_count"],
                "chunk_count": report["chunk_count"],
                "changed_document_count": report["changed_document_count"],
                "changed_chunk_count": report["changed_chunk_count"],
                "field_update_counts": report["field_update_counts"],
                "direct_source_identity_after": report["direct_source_identity_after"],
                "generic_identity": report["generic_identity"],
                "runtime_rebuild_requirement": report["runtime_rebuild_requirement"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
