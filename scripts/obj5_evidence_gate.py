"""Evaluate an Obj5 evidence-selection report against the frozen Obj4 baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "eval" / "retrieval" / "obj4_replacement_baseline.json"


def evaluate(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> dict[str, Any]:
    score = candidate["scorecard"]
    floor = baseline.get("scorecard") or baseline["full_chain"]
    config = candidate.get("evidence_selection_config") or {}
    baseline_config = baseline.get("evidence_selection_config") or {}
    corpus = candidate.get("corpus") or {}
    baseline_corpus = baseline.get("corpus") or {}
    baseline_count = baseline_corpus.get("actual_chunk_count") or baseline_corpus.get("chunk_count")
    corrected_baseline = isinstance(baseline.get("scorecard"), Mapping)
    checks = {
        "selector_enabled": config.get("enabled") is True,
        "baseline_selector_disabled": baseline_config.get("enabled") is False if corrected_baseline else True,
        "model_reranker_disabled": config.get("rerank_enabled") is False,
        "corpus_parity": int(corpus.get("actual_chunk_count") or 0) == int(baseline_count or 0),
        "retrieval_recall_preserved": float(score["recall_at_10"]) >= float(floor["recall_at_10"]),
        "completeness_improved": float(score["completeness_rate"]) > float(floor["completeness_rate"]),
        "v2_faithfulness_preserved": float(score["v2_faithfulness_rate"]) >= float(floor["v2_faithfulness_rate"]),
        "sentence_completeness_preserved": float(score["sentence_completeness_rate"])
        >= float(floor["sentence_completeness_rate"]),
        "citation_alignment_complete": float(score.get("citation_alignment_rate") or 0.0) == 1.0,
        "baseline_citation_alignment_complete": (
            float(floor.get("citation_alignment_rate") or 0.0) == 1.0 if corrected_baseline else True
        ),
    }
    return {
        "schema_version": "phase5.obj5_evidence_gate.v1",
        "eligible": all(checks.values()),
        "checks": checks,
        "baseline_floor": floor,
        "candidate_scorecard": score,
        "evidence_selection_config": dict(config),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    report = evaluate(candidate, baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"eligible": report["eligible"], "checks": report["checks"]}, indent=2))
    return 0 if report["eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
