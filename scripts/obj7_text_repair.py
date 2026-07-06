"""Apply Obj7 corpus text repairs from a versioned manifest."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.ingestion.chunking import estimate_tokens  # noqa: E402

DEFAULT_REPAIRS = ROOT / "configs" / "corpus_text_repairs.yaml"
DEFAULT_CHUNKS_DIR = ROOT / "data" / "chunks"
DEFAULT_OUTPUT = ROOT / "run_logs" / "obj7_text_repair.json"
REPORT_SCHEMA = "phase5.obj7.text_repair.report.v1"
REPAIR_SCHEMA = "phase5.corpus_text_repairs.v1"


def configure_stdout_utf8() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except Exception:
        return


def load_repairs(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping) or data.get("schema_version") != REPAIR_SCHEMA:
        raise ValueError(f"Unsupported text repair manifest: {path}")
    repairs = data.get("repairs")
    if not isinstance(repairs, list):
        raise ValueError(f"{path} must contain a repairs list.")
    return [dict(repair) for repair in repairs if isinstance(repair, Mapping)]


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


def run_text_repairs(
    *,
    repairs: Sequence[Mapping[str, Any]],
    chunks_dir: Path = DEFAULT_CHUNKS_DIR,
    execute: bool = False,
) -> dict[str, Any]:
    paths = sorted(chunks_dir.glob("*/*/chunks.jsonl"))
    repair_by_chunk = {str(repair.get("chunk_id")): dict(repair) for repair in repairs if repair.get("chunk_id")}
    results: list[dict[str, Any]] = []
    touched_files: set[str] = set()
    changed_chunks = 0

    for path in paths:
        rows = read_jsonl(path)
        changed = False
        for index, row in enumerate(rows):
            repair = repair_by_chunk.get(str(row.get("chunk_id") or ""))
            if not repair:
                continue
            new_row, result = apply_repair(row, repair)
            result["chunks_path"] = _rel(path)
            results.append(result)
            if new_row != row:
                rows[index] = new_row
                changed = True
                changed_chunks += 1
        if changed:
            touched_files.add(_rel(path))
            if execute:
                write_jsonl(path, rows)

    missing = sorted(set(repair_by_chunk) - {str(result["chunk_id"]) for result in results})
    return {
        "schema_version": REPORT_SCHEMA,
        "mode": "execute" if execute else "dry_run",
        "repair_count": len(repair_by_chunk),
        "matched_repair_count": len(results),
        "missing_chunk_ids": missing,
        "changed_chunk_count": changed_chunks,
        "touched_files": sorted(touched_files),
        "repairs": results,
    }


def apply_repair(row: Mapping[str, Any], repair: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = dict(row)
    fields = [str(field) for field in repair.get("fields", []) if str(field)]
    field_results: dict[str, str] = {}
    for field in fields:
        value = updated.get(field)
        if not isinstance(value, str):
            field_results[field] = "missing_or_non_text"
            continue
        repaired, status = _repair_text(value, repair)
        field_results[field] = status
        if repaired != value:
            updated[field] = repaired
    if updated != row:
        _stamp_repair(updated, repair)
        text = str(updated.get("text") or "")
        updated["char_count"] = len(text)
        updated["token_estimate"] = estimate_tokens(text)
    return updated, {
        "repair_id": repair.get("id"),
        "chunk_id": row.get("chunk_id"),
        "doc_id": row.get("doc_id"),
        "field_status": field_results,
        "changed": updated != row,
    }


def _repair_text(value: str, repair: Mapping[str, Any]) -> tuple[str, str]:
    replacement = str(repair.get("replacement") or "")
    if replacement and replacement in value and "\ufffd" not in value:
        return value, "already_applied"
    start = _find_marker(value, _start_markers(repair))
    end_marker = str(repair.get("end_marker") or "")
    if start is None or not end_marker:
        return value, "markers_missing"
    end = value.find(end_marker, start[1])
    if end < 0:
        return value, "markers_missing"
    repaired = value[: start[1]] + replacement + value[end:]
    return repaired, "changed" if repaired != value else "unchanged"


def _start_markers(repair: Mapping[str, Any]) -> list[str]:
    markers = [str(repair.get("start_marker") or "")]
    alternates = repair.get("start_marker_alternates")
    if isinstance(alternates, list):
        markers.extend(str(item) for item in alternates if str(item))
    return [marker for marker in markers if marker]


def _find_marker(value: str, markers: Sequence[str]) -> tuple[int, int] | None:
    matches = [(index, index + len(marker)) for marker in markers if (index := value.find(marker)) >= 0]
    return min(matches) if matches else None


def _stamp_repair(row: dict[str, Any], repair: Mapping[str, Any]) -> None:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    repairs = metadata.get("corpus_text_repairs")
    if not isinstance(repairs, list):
        repairs = []
    repair_id = str(repair.get("id") or "")
    if repair_id and repair_id not in repairs:
        repairs.append(repair_id)
    metadata["corpus_text_repairs"] = repairs
    row["metadata"] = metadata


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    configure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repairs", type=Path, default=DEFAULT_REPAIRS)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = run_text_repairs(
        repairs=load_repairs(args.repairs),
        chunks_dir=args.chunks_dir,
        execute=args.execute,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "mode": report["mode"],
                "repair_count": report["repair_count"],
                "matched_repair_count": report["matched_repair_count"],
                "changed_chunk_count": report["changed_chunk_count"],
                "missing_chunk_ids": report["missing_chunk_ids"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not report["missing_chunk_ids"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
