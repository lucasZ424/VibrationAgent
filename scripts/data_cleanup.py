"""Audit and clean local data artifacts.

Default mode is a dry run. Pass --execute to delete matched paths.
"""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Candidate:
    path: Path
    reason: str


def _workspace(path: str | Path | None) -> Path:
    return Path(path or ".").resolve()


def _size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except OSError:
                pass
    return total


def _inside(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _existing(paths: Iterable[Candidate]) -> list[Candidate]:
    return [candidate for candidate in paths if candidate.path.exists()]


def _candidates(root: Path, *, profile: str, include_chunks: bool, include_cache: bool) -> list[Candidate]:
    data = root / "data"
    candidates: list[Candidate] = [
        Candidate(data / "tmp", "temporary working files"),
        Candidate(data / "run_logs", "diagnostic run logs"),
        Candidate(data / "answer_logs", "manual answer snapshots"),
        Candidate(data / "exports" / ".pytest_tmp_safe", "pytest temporary workspace"),
        Candidate(root / ".pytest_cache", "pytest cache"),
    ]
    candidates.extend(
        Candidate(path, "pytest cache spill directory")
        for path in root.glob("pytest-cache-files-*")
        if path.is_dir()
    )

    if profile in {"regenerable", "deep"}:
        candidates.extend(
            [
                Candidate(data / "ocr", "regenerable OCR page exports"),
                Candidate(data / "extracted", "regenerable extracted figures/tables"),
                Candidate(data / "exports", "regenerable manifests and API contexts"),
                Candidate(data / "embeddings", "regenerable embedding exports"),
            ]
        )
    if include_chunks or profile == "deep":
        candidates.append(Candidate(data / "chunks", "regenerable chunk exports; keep if using file-backed retrieval"))
    if include_cache:
        candidates.append(Candidate(data / "cache", "downloaded model cache; may require re-download"))
    return _existing(candidates)


def _delete(candidate: Candidate, root: Path) -> None:
    path = candidate.path.resolve()
    if not _inside(root, path):
        raise RuntimeError(f"Refusing to delete outside workspace: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit and clean local data artifacts.")
    parser.add_argument("--workspace", default=".", help="Workspace root. Defaults to current directory.")
    parser.add_argument(
        "--profile",
        choices=["diagnostics", "regenerable", "deep"],
        default="diagnostics",
        help="diagnostics cleans logs/temp; regenerable also cleans OCR/extracted/exports; deep also includes chunks.",
    )
    parser.add_argument("--include-chunks", action="store_true", help="Clean data/chunks even outside deep profile.")
    parser.add_argument("--include-cache", action="store_true", help="Clean downloaded model cache.")
    parser.add_argument("--execute", action="store_true", help="Actually delete paths. Omit for dry run.")
    args = parser.parse_args(argv)

    root = _workspace(args.workspace)
    candidates = _candidates(root, profile=args.profile, include_chunks=args.include_chunks, include_cache=args.include_cache)
    rows = [
        {
            "path": str(candidate.path),
            "reason": candidate.reason,
            "size_bytes": _size(candidate.path),
        }
        for candidate in candidates
    ]
    if args.execute:
        for candidate in candidates:
            _delete(candidate, root)

    print(
        json.dumps(
            {
                "status": "deleted" if args.execute else "dry_run",
                "profile": args.profile,
                "workspace": str(root),
                "candidate_count": len(rows),
                "total_size_bytes": sum(row["size_bytes"] for row in rows),
                "candidates": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
