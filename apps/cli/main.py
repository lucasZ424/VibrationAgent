"""Minimal CLI entry for Phase-0 development."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from apps._bootstrap import ensure_local_imports

ensure_local_imports(__file__)

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.ingestion.pipeline import chunk_documents, ingest as plan_ingestion  # noqa: E402
from vibration_agent.ingestion.pipeline import parse_pages as parse_input_pages  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.schemas import PHASE0_ACTIVE_SKILLS, PHASE0_DEFERRED_SKILLS, SkillOutput  # noqa: E402

_STATUS_EXIT_CODES = {"ok": 0, "insufficient": 2, "fail": 1}


def _configure_stdout_utf8() -> None:
    """Best-effort UTF-8 stdout for Windows redirected CLI JSON."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        reconfigure(encoding="utf-8")
    except Exception:
        return


def _print_json(payload: Any, *, pretty: bool = True, output: Path | None = None) -> None:
    text = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        if pretty
        else json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    if output is None:
        print(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")


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
    parser.add_argument("--output", type=Path, default=None, help="Write command JSON directly as UTF-8")


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
    parse.add_argument("--output", type=Path, default=None, help="Write command JSON directly as UTF-8")

    ask = sub.add_parser("ask", help="Ask the Tutor-Orchestrator a question")
    ask.add_argument("query")
    ask.add_argument("--chunks-jsonl", action="append", default=[], help="Path to one S1 chunks.jsonl export; may be repeated")
    ask.add_argument("--chunks-dir", default=None, help="Directory containing chunks.jsonl exports")
    ask.add_argument("--top-k", type=int, default=None, help="Number of retrieval hits to use")
    ask.add_argument("--scope", choices=["in_scope", "out_of_scope"], default=None, help="Override domain scope for this query")
    ask.add_argument("--domain-scope", choices=["in_scope", "out_of_scope"], default=None, help="Alias for --scope")
    ask.add_argument("--output", type=Path, default=None, help="Write command JSON directly as UTF-8")

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdout_utf8()
    parser = _build_parser()
    args = parser.parse_args(argv)
    pretty = not args.compact_json
    output_path = getattr(args, "output", None)

    try:
        settings = load(args.workspace)

        if args.cmd == "config":
            _print_json(_with_workspace(settings.model_dump(mode="json"), settings), pretty=pretty, output=output_path)
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
                output=output_path,
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
            _print_json(result, pretty=pretty, output=output_path)
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
            _print_json(result, pretty=pretty, output=output_path)
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
            skill_output = TutorOrchestrator().handle_query(args.query, constraints=constraints)
            payload = _with_workspace(skill_output.model_dump(mode="json"), settings)
            _print_json(payload, pretty=pretty, output=output_path)
            return _exit_code(skill_output.status)
    except Exception as exc:
        failed_workspace = settings.paths.workspace if "settings" in locals() else args.workspace
        _print_json(_fail_payload(args.cmd, exc, failed_workspace), pretty=pretty, output=output_path)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
