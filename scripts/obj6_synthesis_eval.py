"""Prepare and evaluate the Phase-5 Obj6A replay-first S3 lane."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.rag_qa_eval import (  # noqa: E402
    _offline_settings,
    load_questions,
    run_rag_qa_eval,
)
from vibration_agent.config import load  # noqa: E402
from vibration_agent.llm.replay import ReplayClient, request_from_kwargs  # noqa: E402
from vibration_agent.orchestrator.tutor import TutorOrchestrator  # noqa: E402
from vibration_agent.retrieval.hybrid import load_runtime_chunks  # noqa: E402
from vibration_agent.skills.s2_retrieval import RetrievalSkill  # noqa: E402
from vibration_agent.skills.s3_qa_summary import QASummarySkill  # noqa: E402

HARD_CASE_IDS = {
    "p5_comparison_zh_unbalance_misalignment",
    "p5_comparison_en_unbalance_misalignment",
    "p5_diagnosis_zh_fault_discrimination",
    "p5_diagnosis_en_fault_discrimination",
}


class _RequestProbe:
    def __init__(self) -> None:
        self.calls: dict[str, dict[str, Any]] = {}

    def synthesize(self, **kwargs: Any) -> dict[str, Any]:
        self.calls[str(kwargs["task_id"])] = kwargs
        return {"status": "insufficient", "answer": "", "claims": []}


def prepare_requests(*, output_dir: Path) -> dict[str, Any]:
    settings = _offline_settings(load(ROOT))
    chunks = load_runtime_chunks(settings)
    if not chunks:
        raise RuntimeError("Local Qdrant corpus is unavailable or empty.")
    questions = load_questions()
    probe = _RequestProbe()
    orchestrator = TutorOrchestrator(
        settings=settings,
        retrieval_skill=RetrievalSkill(settings=settings),
        qa_summary_skill=QASummarySkill(settings=settings, llm_client=probe),
    )
    for case in questions["cases"]:
        if case["case_id"] not in HARD_CASE_IDS:
            continue
        orchestrator.handle_query(
            str(case["query"]),
            task_id=str(case["case_id"]),
            user_mode="engineering",
            context={"chunks": list(chunks)},
            constraints={
                "top_k": 10,
                "difficulty": "low",
                "s3_llm_enabled": True,
                "s4_enabled": False,
                "advisory_routing_enabled": False,
            },
        )
    if set(probe.calls) != HARD_CASE_IDS:
        raise RuntimeError(f"Expected four hard-case requests, produced {sorted(probe.calls)}")
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for case_id in sorted(probe.calls):
        kwargs = probe.calls[case_id]
        path = output_dir / f"{case_id}.json"
        path.write_text(json.dumps(kwargs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        request = request_from_kwargs(task="s3_qa_summary", schema_version="s3.v1", kwargs=kwargs)
        rows.append({"case_id": case_id, "request_json": str(path), "request_hash": request.request_hash})
    manifest = {"schema_version": "phase5.obj6a.requests.v1", "corpus_count": len(chunks), "requests": rows}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def run_replay(*, replay_dir: Path) -> dict[str, Any]:
    settings = _offline_settings(load(ROOT))
    chunks = load_runtime_chunks(settings)
    client = ReplayClient(replay_dir)
    orchestrator = TutorOrchestrator(
        settings=settings,
        retrieval_skill=RetrievalSkill(settings=settings),
        qa_summary_skill=QASummarySkill(settings=settings, llm_client=client),
    )

    def runner(case: Mapping[str, Any]):
        enabled = case["case_id"] in HARD_CASE_IDS
        return orchestrator.handle_query(
            str(case["query"]), task_id=str(case["case_id"]), user_mode="engineering",
            context={"chunks": list(chunks)},
            constraints={"top_k": 10, "difficulty": "low", "s3_llm_enabled": enabled,
                         "llm_enabled": False, "advisory_routing_enabled": False},
        )

    return run_rag_qa_eval(
        questions=load_questions(), query_runner=runner, corpus_count=len(chunks),
        evidence_selection_config={"enabled": False, "rerank_enabled": False},
    )


def evaluate_gate(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    score, floor = candidate["scorecard"], baseline["scorecard"]
    base_cases = {row["case_id"]: row for row in baseline["cases"]}
    cand_cases = {row["case_id"]: row for row in candidate["cases"]}
    hard_gain = sum(cand_cases[key]["completeness"] for key in HARD_CASE_IDS) > sum(
        base_cases[key]["completeness"] for key in HARD_CASE_IDS
    )
    no_complete_miss = all(
        not (float(row["completeness"]) > 0 and float(cand_cases[key]["completeness"]) == 0)
        for key, row in base_cases.items()
    )
    checks = {
        "corpus_parity": candidate["corpus"]["actual_chunk_count"] == baseline["corpus"]["actual_chunk_count"],
        "recall_at_10_preserved": score["recall_at_10"] == floor["recall_at_10"],
        "completeness_improved": score["completeness_rate"] > floor["completeness_rate"],
        "v2_faithfulness_preserved": score["v2_faithfulness_rate"] == 1.0,
        "sentence_completeness_preserved": (
            score["sentence_completeness_rate"] >= floor["sentence_completeness_rate"]
        ),
        "citation_alignment_complete": score["citation_alignment_rate"] == 1.0,
        "semantic_hard_cases_improved": hard_gain,
        "no_complete_case_miss": no_complete_miss,
    }
    return {"schema_version": "phase5.obj6a.gate.v1", "eligible": all(checks.values()), "checks": checks,
            "baseline_scorecard": floor, "candidate_scorecard": score}


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--output-dir", type=Path, required=True)
    replay = sub.add_parser("evaluate")
    replay.add_argument("--replay-dir", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--candidate", type=Path, required=True)
    gate.add_argument("--baseline", type=Path, required=True)
    gate.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        report = prepare_requests(output_dir=args.output_dir)
    elif args.command == "evaluate":
        report = run_replay(replay_dir=args.replay_dir)
        _write(args.output, report)
    else:
        report = evaluate_gate(_read(args.candidate), _read(args.baseline))
        _write(args.output, report)
    print(json.dumps({key: report[key] for key in report if key in {"schema_version", "eligible", "checks", "corpus_count"}}, indent=2))
    return 1 if report.get("eligible") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
