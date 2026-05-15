"""Minimal CLI entry for Phase-0 development."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _ensure_local_src_importable() -> None:
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_local_src_importable()

from vibration_agent.config import load  # noqa: E402
from vibration_agent.ingestion.pipeline import ingest as plan_ingestion  # noqa: E402
from vibration_agent.ingestion.pipeline import parse_pages as parse_input_pages  # noqa: E402
from vibration_agent.schemas import PHASE0_ACTIVE_SKILLS, PHASE0_DEFERRED_SKILLS  # noqa: E402


def _settings_json(workspace: Path | None = None) -> str:
    settings = load(workspace)
    return json.dumps(settings.model_dump(mode="json"), ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vib-agent")
    parser.add_argument("--workspace", type=Path, default=None, help="Project workspace root")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("config", help="Print resolved runtime settings")
    sub.add_parser("scope", help="Print Phase-0 active and deferred skills")

    ingest = sub.add_parser("ingest", help="Ingest a file or directory into the KB")
    ingest.add_argument("path")

    parse = sub.add_parser("parse-pages", help="Parse/OCR PDFs into page-level JSONL")
    parse.add_argument("path")
    parse.add_argument("--max-pages", type=int, default=None)
    parse.add_argument("--no-write", action="store_true")
    parse.add_argument("--keep-images", action="store_true")

    ask = sub.add_parser("ask", help="Ask the orchestrator a question")
    ask.add_argument("query")

    args = parser.parse_args(argv)
    settings = load(args.workspace)

    if args.cmd == "config":
        print(_settings_json(args.workspace))
    elif args.cmd == "scope":
        print(
            json.dumps(
                {
                    "active_skills": PHASE0_ACTIVE_SKILLS,
                    "deferred_skills": PHASE0_DEFERRED_SKILLS,
                    "phase0_pipeline": settings.phase0_pipeline,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.cmd == "ingest":
        plan = plan_ingestion(args.path)
        plan["workspace"] = str(settings.paths.workspace)
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    elif args.cmd == "parse-pages":
        result = parse_input_pages(
            args.path,
            max_pages=args.max_pages,
            write_output=not args.no_write,
            keep_images=args.keep_images,
            settings=settings,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.cmd == "ask":
        # TODO(S3): call vibration_agent.orchestrator.tutor once target 15 is active.
        print(
            json.dumps(
                {
                    "status": "stub",
                    "command": "ask",
                    "query": args.query,
                    "pipeline": settings.phase0_pipeline,
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())