"""Phase-4 Obj4 Qdrant reindex and retrieval replacement gate.

This runner evaluates whether the Obj2 retrieval replacement gate permits a
Qdrant reindex/replacement attempt. It does not perform live Qdrant writes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from scripts.retrieval_eval import DEFAULT_CHUNKS_DIR, DEFAULT_TARGETS, load_targets, run_retrieval_eval  # noqa: E402
from vibration_agent.config import Settings, load  # noqa: E402


def evaluate_reindex_gate(
    *,
    retrieval_report: Mapping[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_report = dict(retrieval_report or run_retrieval_eval())
    active_settings = settings or load()
    replacement_gate = active_report.get("replacement_gate")
    if not isinstance(replacement_gate, Mapping):
        raise ValueError("Retrieval report is missing replacement_gate.")

    replacement_allowed = bool(replacement_gate.get("replacement_justified_by_baseline"))
    embedding_ready = bool(active_settings.embeddings.enabled)
    qdrant_ready = bool(active_settings.database.qdrant_enabled)
    reindex_allowed = replacement_allowed and embedding_ready and qdrant_ready
    return {
        "schema_version": "phase4.obj4_qdrant_reindex_gate.v1",
        "retrieval_eval_schema_version": active_report.get("schema_version"),
        "decision": "reindex_allowed" if reindex_allowed else "non_replacement",
        "replacement": {
            "allowed": replacement_allowed,
            "reason": _replacement_reason(replacement_gate, replacement_allowed),
            "gate": dict(replacement_gate),
        },
        "reindex": {
            "allowed": reindex_allowed,
            "executed": False,
            "reason": _reindex_reason(
                replacement_allowed=replacement_allowed,
                embedding_ready=embedding_ready,
                qdrant_ready=qdrant_ready,
            ),
        },
        "runtime_settings": {
            "embedding_enabled": active_settings.embeddings.enabled,
            "embedding_provider": active_settings.embeddings.provider,
            "embedding_model": active_settings.embeddings.model_name,
            "embedding_model_version": active_settings.embeddings.model_version,
            "qdrant_enabled": active_settings.database.qdrant_enabled,
            "qdrant_collection": active_settings.database.qdrant_collection,
            "qdrant_vector_size": active_settings.database.qdrant_vector_size,
        },
        "retrieval_scorecard": active_report.get("scorecard", {}),
        "missing_evidence_cases": active_report.get("missing_evidence_cases", []),
        "attribution_summary": _attribution_summary(active_report),
    }


def _replacement_reason(gate: Mapping[str, Any], allowed: bool) -> str:
    if allowed:
        return "Obj2 retrieval replacement gate is satisfied by the baseline report."
    top_k = gate.get("decision_top_k")
    recall = gate.get("baseline_recall_at_decision_top_k")
    threshold = gate.get("minimum_recall_at_decision_top_k")
    missing = gate.get("baseline_missing_evidence_case_count")
    missing_threshold = gate.get("missing_evidence_case_threshold")
    return (
        f"Obj2 retrieval replacement gate is not satisfied: top_k_recall@{top_k}={recall} "
        f"is not below {threshold}, and missing_evidence_cases={missing} is below {missing_threshold}."
    )


def _reindex_reason(*, replacement_allowed: bool, embedding_ready: bool, qdrant_ready: bool) -> str:
    if not replacement_allowed:
        return "Reindex is blocked because retrieval replacement is not justified by Obj2/Obj3 evidence."
    missing = []
    if not embedding_ready:
        missing.append("embedding provider is not explicitly enabled")
    if not qdrant_ready:
        missing.append("Qdrant is not explicitly enabled")
    if missing:
        return "Reindex is blocked because " + " and ".join(missing) + "."
    return "Reindex may proceed only through a separate explicit operator command."


def _attribution_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for case in report.get("cases", []) or []:
        if not isinstance(case, Mapping):
            continue
        diagnostics = case.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        contributions = diagnostics.get("top_hit_contributions")
        if not isinstance(contributions, list):
            continue
        for contribution in contributions:
            if not isinstance(contribution, Mapping):
                continue
            name = str(contribution.get("contribution") or "unknown")
            counts[name] = counts.get(name, 0) + 1
    return {"top_hit_contribution_counts": counts}


def _load_report(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Phase-4 Obj4 Qdrant reindex gate.")
    parser.add_argument("--retrieval-report", type=Path, default=None)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = _load_report(args.retrieval_report)
    if report is None:
        report = run_retrieval_eval(targets=load_targets(args.targets), chunks_dir=args.chunks_dir)
    gate = evaluate_reindex_gate(retrieval_report=report)
    text = json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
