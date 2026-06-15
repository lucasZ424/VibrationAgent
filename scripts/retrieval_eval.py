"""Offline retrieval recall audit for Phase-4 Obj2.

The runner consumes labeled retrieval targets and existing chunk fixtures. It
uses the real hybrid retrieval path and never calls live providers.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.retrieval.hybrid import load_chunks, search  # noqa: E402

DEFAULT_TARGETS = ROOT / "tests" / "fixtures" / "retrieval" / "targets.json"
DEFAULT_CHUNKS_DIR = ROOT / "tests" / "fixtures" / "chunks"


def load_targets(path: Path = DEFAULT_TARGETS) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    targets = data.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"{path} must contain a non-empty targets array.")
    return data


def run_retrieval_eval(
    *,
    targets: Mapping[str, Any] | None = None,
    chunks: Sequence[Mapping[str, Any]] | None = None,
    chunk_paths: Sequence[str | Path] | None = None,
    chunks_dir: str | Path | None = DEFAULT_CHUNKS_DIR,
) -> dict[str, Any]:
    active_targets = targets if targets is not None else load_targets()
    target_rows = active_targets.get("targets")
    if not isinstance(target_rows, list) or not target_rows:
        raise ValueError("Retrieval targets must contain a non-empty targets array.")

    corpus = load_chunks(
        chunks=chunks,
        chunk_paths=_chunk_paths(chunk_paths=chunk_paths, chunks_dir=chunks_dir),
    )
    required_top_k = _required_top_k(active_targets, target_rows)
    max_top_k = max(required_top_k)
    cases = [_run_case(target, corpus=corpus, top_k_values=required_top_k, max_top_k=max_top_k) for target in target_rows]
    evidence_cases = [case for case in cases if case["expected_evidence_count"] > 0]
    expected_miss_cases = [case for case in cases if case["expected_evidence_count"] == 0]
    missing_evidence_cases = [
        case["case_id"]
        for case in evidence_cases
        if not all(case["recall_at_k"].get(str(k), False) for k in required_top_k)
    ]
    unexpected_expected_miss_hits = [
        case["case_id"]
        for case in expected_miss_cases
        if case["failure_type"] == "unexpected_hit_for_expected_miss"
    ]
    replacement_gate = _replacement_gate(
        evidence_cases=evidence_cases,
        required_top_k=required_top_k,
        missing_evidence_cases=missing_evidence_cases,
    )
    return {
        "schema_version": "phase4.retrieval_eval.report.v1",
        "target_schema_version": active_targets.get("schema_version"),
        "case_count": len(cases),
        "evidence_case_count": len(evidence_cases),
        "expected_miss_case_count": len(expected_miss_cases),
        "chunk_count": len(corpus),
        "required_top_k": required_top_k,
        "scorecard": {
            f"top_k_recall@{k}": _recall_at_k(evidence_cases, k) for k in required_top_k
        },
        "replacement_gate": replacement_gate,
        "missing_evidence_cases": missing_evidence_cases,
        "expected_miss_cases": [case["case_id"] for case in expected_miss_cases],
        "unexpected_expected_miss_hits": unexpected_expected_miss_hits,
        "cases": cases,
    }


def _replacement_gate(
    *,
    evidence_cases: Sequence[Mapping[str, Any]],
    required_top_k: Sequence[int],
    missing_evidence_cases: Sequence[str],
) -> dict[str, Any]:
    decision_top_k = 10 if 10 in required_top_k else max(required_top_k)
    recall_at_decision_k = _recall_at_k(evidence_cases, decision_top_k)
    threshold = 0.8
    missing_threshold = 1
    replacement_justified = bool(
        recall_at_decision_k is not None
        and (
            recall_at_decision_k < threshold
            or len(missing_evidence_cases) >= missing_threshold
        )
    )
    return {
        "decision_top_k": decision_top_k,
        "minimum_recall_at_decision_top_k": threshold,
        "missing_evidence_case_threshold": missing_threshold,
        "baseline_recall_at_decision_top_k": recall_at_decision_k,
        "baseline_missing_evidence_case_count": len(missing_evidence_cases),
        "replacement_justified_by_baseline": replacement_justified,
        "rule": (
            "Obj4 retrieval replacement is justified only if baseline "
            f"top_k_recall@{decision_top_k} < {threshold:.2f} or "
            f"missing_evidence_cases >= {missing_threshold}; a candidate must "
            "fix at least one miss without lowering recall on other evidence targets."
        ),
    }


def _chunk_paths(
    *,
    chunk_paths: Sequence[str | Path] | None,
    chunks_dir: str | Path | None,
) -> list[Path]:
    paths = [Path(path) for path in chunk_paths or []]
    if chunks_dir is not None:
        paths.extend(sorted(Path(chunks_dir).glob("*.jsonl")))
    return paths


def _required_top_k(active_targets: Mapping[str, Any], target_rows: Sequence[Any]) -> list[int]:
    values: set[int] = set()
    for value in active_targets.get("default_required_top_k", []) or []:
        values.add(int(value))
    for target in target_rows:
        if isinstance(target, Mapping):
            for value in target.get("required_top_k", []) or []:
                values.add(int(value))
    if not values:
        values.add(10)
    return sorted(k for k in values if k > 0)


def _run_case(
    target: Any,
    *,
    corpus: Sequence[Mapping[str, Any]],
    top_k_values: Sequence[int],
    max_top_k: int,
) -> dict[str, Any]:
    if not isinstance(target, Mapping):
        raise ValueError("Each retrieval target must be an object.")
    case_id = str(target.get("case_id") or "unknown")
    expected = _expected_evidence(target)
    result = search(str(target.get("query") or ""), chunks=corpus, top_k=max_top_k)
    hits = result.get("hits") if isinstance(result.get("hits"), list) else []
    contexts = result.get("retrieval_context") if isinstance(result.get("retrieval_context"), list) else []
    hit_ids = [str(hit.get("chunk_id")) for hit in hits if isinstance(hit, Mapping)]
    expected_ids = [item["chunk_id"] for item in expected]
    matched_by_k = {
        str(k): [chunk_id for chunk_id in expected_ids if chunk_id in set(hit_ids[:k])]
        for k in top_k_values
    }
    recall_at_k = {str(k): bool(matched_by_k[str(k)]) for k in top_k_values}
    expected_status = str(target.get("expected_status") or ("ok" if expected else "insufficient"))
    if expected:
        failure_type = "retrieval_hit" if any(recall_at_k.values()) else "retrieval_miss"
    elif hits:
        failure_type = "unexpected_hit_for_expected_miss"
    else:
        failure_type = "expected_miss"
    return {
        "case_id": case_id,
        "query": str(target.get("query") or ""),
        "intent": target.get("intent"),
        "expected_status": expected_status,
        "actual_status": result.get("status"),
        "failure_type": failure_type,
        "expected_evidence_count": len(expected),
        "expected_chunk_ids": expected_ids,
        "hit_chunk_ids": hit_ids,
        "matched_expected_by_k": matched_by_k,
        "recall_at_k": recall_at_k,
        "warnings": result.get("warnings", []),
        "diagnostics": {
            "normalized_query": result.get("normalized_query"),
            "detected_terms": result.get("detected_terms", []),
            "detected_symbols": result.get("detected_symbols", []),
            "top_hit_reasons": [
                str(hit.get("reason") or "")
                for hit in hits[: min(len(hits), 3)]
                if isinstance(hit, Mapping)
            ],
            "top_hit_contributions": [
                {
                    "chunk_id": context.get("chunk_id"),
                    "contribution": context.get("retrieval_contribution"),
                    "lanes": context.get("retrieval_lanes", []),
                    "lane_scores": context.get("lane_scores", {}),
                }
                for context in contexts[: min(len(contexts), 3)]
                if isinstance(context, Mapping)
            ],
            "synthesis_evaluated": False,
        },
    }


def _expected_evidence(target: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = target.get("expected_evidence")
    if not isinstance(raw, list):
        return []
    evidence: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping) and item.get("chunk_id"):
            evidence.append(
                {
                    "chunk_id": str(item["chunk_id"]),
                    "doc_id": str(item.get("doc_id") or ""),
                    "pages": list(item.get("pages") or []),
                }
            )
    return evidence


def _recall_at_k(cases: Sequence[Mapping[str, Any]], k: int) -> float | None:
    if not cases:
        return None
    return sum(1 for case in cases if case["recall_at_k"].get(str(k))) / len(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Phase-4 retrieval recall audit.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--chunk-path", action="append", type=Path, default=[])
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_retrieval_eval(
        targets=load_targets(args.targets),
        chunk_paths=args.chunk_path,
        chunks_dir=args.chunks_dir,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if not report["missing_evidence_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
