"""Minimal CLI entry for Phase-0 development."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _ensure_local_src_importable() -> None:
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    for path in (root, src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


_ensure_local_src_importable()

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.ingestion.pipeline import chunk_documents, ingest as plan_ingestion  # noqa: E402
from vibration_agent.ingestion.pipeline import parse_pages as parse_input_pages  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import PHASE0_ACTIVE_SKILLS, PHASE0_DEFERRED_SKILLS, SkillOutput  # noqa: E402

_STATUS_EXIT_CODES = {"ok": 0, "insufficient": 2, "fail": 1}


def _print_json(payload: Any, *, pretty: bool = True) -> None:
    if pretty:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _exit_code(status: str | None) -> int:
    return _STATUS_EXIT_CODES.get(status or "fail", 1)


def _with_workspace(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    return {"workspace": str(settings.paths.workspace), **payload}


def _fail_payload(command: str | None, exc: Exception, workspace: Path | None) -> dict[str, Any]:
    return {
        "status": "fail",
        "command": command,
        "workspace": str(workspace) if workspace is not None else None,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def _add_common_ingestion_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("path")
    parser.add_argument("--source-type", default="book", help="Source type namespace for structured outputs")
    parser.add_argument("--max-pages", type=int, default=None, help="Limit parsed pages per document")
    parser.add_argument("--no-recursive", action="store_true", help="Only scan the top-level directory")
    parser.add_argument("--no-write", action="store_true", help="Do not write structured output files")
    parser.add_argument("--keep-images", action="store_true", help="Keep rendered page images for OCR PDFs")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vib-agent")
    parser.add_argument("--workspace", type=Path, default=None, help="Project workspace root")
    parser.add_argument("--compact-json", action="store_true", help="Print compact JSON instead of indented JSON")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config", help="Print resolved runtime settings")
    sub.add_parser("scope", help="Print Phase-0 active and deferred skills")

    ingest_parser = sub.add_parser("ingest", help="Build structured document exports for S2 retrieval")
    _add_common_ingestion_args(ingest_parser)
    ingest_parser.add_argument("--plan-only", action="store_true", help="Only classify inputs; do not parse or chunk")

    parse = sub.add_parser("parse-pages", help="Parse/OCR PDFs into page-level JSONL")
    parse.add_argument("path")
    parse.add_argument("--max-pages", type=int, default=None)
    parse.add_argument("--no-write", action="store_true")
    parse.add_argument("--keep-images", action="store_true")
    parse.add_argument("--no-recursive", action="store_true")
    parse.add_argument("--source-type", default="book")

    ask = sub.add_parser("ask", help="Ask the Tutor-Orchestrator a question")
    ask.add_argument("query")
    ask.add_argument("--chunks-jsonl", action="append", default=[], help="Path to one S1 chunks.jsonl export; may be repeated")
    ask.add_argument("--chunks-dir", default=None, help="Directory containing chunks.jsonl exports")
    ask.add_argument("--top-k", type=int, default=None, help="Number of retrieval hits to use")
    ask.add_argument("--scope", choices=["in_scope", "out_of_scope"], default=None, help="Override domain scope for this query")
    ask.add_argument("--domain-scope", choices=["in_scope", "out_of_scope"], default=None, help="Alias for --scope")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    pretty = not args.compact_json

    try:
        settings = load(args.workspace)

        if args.cmd == "config":
            _print_json(_with_workspace(settings.model_dump(mode="json"), settings), pretty=pretty)
            return 0
        if args.cmd == "scope":
            _print_json(
                _with_workspace(
                    {
                        "active_skills": PHASE0_ACTIVE_SKILLS,
                        "deferred_skills": PHASE0_DEFERRED_SKILLS,
                        "phase0_pipeline": settings.phase0_pipeline,
                    },
                    settings,
                ),
                pretty=pretty,
            )
            return 0
        if args.cmd == "ingest":
            if args.plan_only:
                result = plan_ingestion(args.path, recursive=not args.no_recursive, settings=settings)
            else:
                result = chunk_documents(
                    args.path,
                    recursive=not args.no_recursive,
                    max_pages=args.max_pages,
                    write_output=not args.no_write,
                    keep_images=args.keep_images,
                    source_type=args.source_type,
                    settings=settings,
                )
            result = _with_workspace(result, settings)
            _print_json(result, pretty=pretty)
            return _exit_code(result.get("status"))
        if args.cmd == "parse-pages":
            result = parse_input_pages(
                args.path,
                recursive=not args.no_recursive,
                max_pages=args.max_pages,
                write_output=not args.no_write,
                keep_images=args.keep_images,
                source_type=args.source_type,
                settings=settings,
            )
            result = _with_workspace(result, settings)
            _print_json(result, pretty=pretty)
            return _exit_code(result.get("status"))
        if args.cmd == "ask":
            constraints: dict[str, Any] = {}
            if args.chunks_jsonl:
                constraints["chunk_paths"] = args.chunks_jsonl
            if args.chunks_dir:
                constraints["chunks_dir"] = args.chunks_dir
            if args.top_k is not None:
                constraints["top_k"] = args.top_k
            scope = args.scope or args.domain_scope
            if scope:
                constraints["scope"] = scope
            output = TutorOrchestrator().handle_query(args.query, constraints=constraints)
            payload = _with_workspace(output.model_dump(mode="json"), settings)
            _print_json(payload, pretty=pretty)
            return _exit_code(output.status)
    except Exception as exc:
        failed_workspace = settings.paths.workspace if "settings" in locals() else args.workspace
        _print_json(_fail_payload(args.cmd, exc, failed_workspace), pretty=pretty)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())