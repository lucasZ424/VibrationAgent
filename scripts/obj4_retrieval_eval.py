"""Evaluate Obj4 lexical, ANN, and independent-lane hybrid retrieval."""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import load  # noqa: E402
from vibration_agent.retrieval import hybrid  # noqa: E402

DEFAULT_QUESTIONS = ROOT / "tests" / "fixtures" / "rag_qa" / "questions.json"
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "rag_qa" / "post_r3_baseline.json"
MODES = ("bm25", "dense", "hybrid")
QueryRunner = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _matched(case: Mapping[str, Any], hits: Sequence[Mapping[str, Any]], k: int) -> list[str]:
    matched: list[str] = []
    for target in case["expected_evidence"]:
        pages = set(target.get("pages") or [])
        for hit in hits[:k]:
            exact = str(hit.get("chunk_id") or "") == str(target.get("chunk_id") or "")
            same_page = str(hit.get("doc_id") or "") == str(target.get("doc_id") or "") and bool(
                pages & set(hit.get("pages") or [])
            )
            if exact or same_page:
                matched.append(str(target["evidence_id"]))
                break
    return matched


def run_obj4_eval(
    *,
    questions: Mapping[str, Any],
    baseline: Mapping[str, Any],
    query_runner: QueryRunner,
) -> dict[str, Any]:
    definitions = {str(case["case_id"]): case for case in questions["cases"]}
    mode_cases: dict[str, list[dict[str, Any]]] = {mode: [] for mode in MODES}
    for mode in MODES:
        for case in questions["cases"]:
            output = query_runner(mode, case)
            hits = [dict(hit) for hit in output.get("hits", []) if isinstance(hit, Mapping)]
            expected_count = len(case["expected_evidence"])
            matched_5 = _matched(case, hits, 5)
            matched_10 = _matched(case, hits, 10)
            mode_cases[mode].append(
                {
                    "case_id": case["case_id"],
                    "language": case["language"],
                    "matched_evidence_at_5": matched_5,
                    "matched_evidence_at_10": matched_10,
                    "recall_at_5": round(len(matched_5) / expected_count, 3),
                    "recall_at_10": round(len(matched_10) / expected_count, 3),
                    "hit_chunk_ids": [str(hit.get("chunk_id") or "") for hit in hits[:10]],
                    "lanes": output.get("lanes", {}),
                    "retrieval_source": output.get("retrieval_source"),
                    "warnings": list(output.get("warnings", [])),
                }
            )
    scorecards = {
        mode: {
            "recall_at_5": round(sum(case["recall_at_5"] for case in cases) / len(cases), 3),
            "recall_at_10": round(sum(case["recall_at_10"] for case in cases) / len(cases), 3),
        }
        for mode, cases in mode_cases.items()
    }
    baseline_cases = {str(case["case_id"]): case for case in baseline["cases"]}
    hybrid_cases = {str(case["case_id"]): case for case in mode_cases["hybrid"]}
    baseline_passes = [case_id for case_id, case in baseline_cases.items() if case["recall_at_10"] == 1.0]
    regressed_passes = [case_id for case_id in baseline_passes if hybrid_cases[case_id]["recall_at_10"] == 0.0]
    fixed_misses = [
        case_id
        for case_id, case in baseline_cases.items()
        if case["recall_at_10"] == 0.0 and hybrid_cases[case_id]["recall_at_10"] > 0.0
    ]
    best_single = max(scorecards["bm25"]["recall_at_10"], scorecards["dense"]["recall_at_10"])
    candidate_eligible = (
        scorecards["hybrid"]["recall_at_10"] >= best_single
        and scorecards["hybrid"]["recall_at_10"] >= float(baseline["scorecard"]["recall_at_10"])
        and bool(fixed_misses)
        and not regressed_passes
    )
    return {
        "schema_version": "phase5.obj4_retrieval_eval.report.v1",
        "case_count": len(definitions),
        "alias_schema_version": "phase5.retrieval_aliases.v1",
        "modes": mode_cases,
        "scorecards": scorecards,
        "replacement_gate": {
            "candidate_eligible": candidate_eligible,
            "best_single_lane_recall_at_10": best_single,
            "post_r3_hybrid_recall_at_10": baseline["scorecard"]["recall_at_10"],
            "fixed_baseline_miss_case_ids": fixed_misses,
            "regressed_baseline_pass_case_ids": regressed_passes,
            "v2_full_chain_validation_required": candidate_eligible,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    settings = load(ROOT)
    if not settings.database.qdrant_enabled:
        raise RuntimeError("Obj4 runtime lane evaluation requires Qdrant.")
    settings.retrieval.independent_lanes_enabled = True
    hybrid.clear_runtime_lexical_cache()

    def runner(mode: str, case: Mapping[str, Any]) -> Mapping[str, Any]:
        settings.retrieval.mode = mode
        return hybrid.search(str(case["query"]), top_k=10, settings=settings)

    report = run_obj4_eval(
        questions=_read(args.questions),
        baseline=_read(args.baseline),
        query_runner=runner,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scorecards": report["scorecards"], "replacement_gate": report["replacement_gate"]}, indent=2))
    return 0 if report["replacement_gate"]["candidate_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
