"""Evaluate the Phase-5 Obj3 Qdrant ANN lane without lexical fallback."""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.retrieval.embeddings import embed_texts  # noqa: E402
from vibration_agent.schemas import EmbeddingRecord  # noqa: E402
from vibration_agent.storage import qdrant  # noqa: E402

DEFAULT_QUESTIONS = ROOT / "tests" / "fixtures" / "rag_qa" / "questions.json"
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "rag_qa" / "post_r3_baseline.json"
Embedder = Callable[..., list[EmbeddingRecord]]
Searcher = Callable[[Sequence[float], int], list[dict[str, Any]]]
Clock = Callable[[], float]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _matched_evidence(case: Mapping[str, Any], hits: Sequence[Mapping[str, Any]]) -> list[str]:
    matched: list[str] = []
    for target in case["expected_evidence"]:
        target_pages = set(target.get("pages") or [])
        for hit in hits:
            exact = str(hit.get("chunk_id") or "") == str(target.get("chunk_id") or "")
            same_page = str(hit.get("doc_id") or "") == str(target.get("doc_id") or "") and bool(
                target_pages & set(hit.get("pages") or [])
            )
            if exact or same_page:
                matched.append(str(target["evidence_id"]))
                break
    return matched


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.5)))
    return round(ordered[index], 3)


def run_ann_eval(
    *,
    questions: Mapping[str, Any],
    post_r3_hybrid_recall_at_10: float,
    settings: Settings,
    searcher: Searcher,
    embedder: Embedder = embed_texts,
    clock: Clock = time.perf_counter,
    top_k: int = 10,
) -> dict[str, Any]:
    if top_k != 10:
        raise ValueError("Obj3 acceptance is fixed at top_k=10.")
    corpus = questions.get("corpus") if isinstance(questions.get("corpus"), Mapping) else {}
    if str(corpus.get("embedding_model")) != settings.embeddings.model_name:
        raise RuntimeError("Question fixture embedding model does not match runtime configuration.")
    if int(corpus.get("embedding_dimension") or 0) != settings.database.qdrant_vector_size:
        raise RuntimeError("Question fixture embedding dimension does not match runtime configuration.")
    cases: list[dict[str, Any]] = []
    for definition in questions["cases"]:
        started = clock()
        records = embedder([str(definition["query"])], settings=settings)
        record = records[0] if records else None
        if record is None or record.provider == "fallback_token_features" or not record.vector:
            raise RuntimeError("ANN evaluation forbids token-feature or empty-vector fallback.")
        if record.dimension != settings.database.qdrant_vector_size:
            raise RuntimeError(
                f"Query embedding dimension {record.dimension} does not match "
                f"Qdrant dimension {settings.database.qdrant_vector_size}."
            )
        if (
            record.model_name != settings.embeddings.model_name
            or record.model_version != settings.embeddings.model_version
        ):
            raise RuntimeError("Query embedding provenance does not match runtime configuration.")
        raw_hits = searcher(record.vector, top_k)
        latency_ms = (clock() - started) * 1000
        hits = [dict(item.get("chunk", {}), score=float(item.get("score") or 0.0)) for item in raw_hits]
        matched = _matched_evidence(definition, hits)
        expected_count = len(definition["expected_evidence"])
        cases.append(
            {
                "case_id": definition["case_id"],
                "intent": definition["intent"],
                "language": definition["language"],
                "query": definition["query"],
                "expected_evidence_count": expected_count,
                "matched_evidence_at_10": matched,
                "recall_at_10": round(len(matched) / expected_count, 3),
                "hit_chunk_ids": [str(hit.get("chunk_id") or "") for hit in hits],
                "latency_ms": round(latency_ms, 3),
            }
        )
    recall = round(sum(case["recall_at_10"] for case in cases) / len(cases), 3)
    by_language = {
        language: round(
            sum(case["recall_at_10"] for case in cases if case["language"] == language)
            / sum(1 for case in cases if case["language"] == language),
            3,
        )
        for language in sorted({str(case["language"]) for case in cases})
    }
    paired: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        paired[str(case["intent"])].append(case)
    pair_passes = [
        {str(case["language"]) for case in pair} == {"zh", "en"}
        and all(case["recall_at_10"] == 1.0 for case in pair)
        for pair in paired.values()
    ]
    latencies = [float(case["latency_ms"]) for case in cases]
    return {
        "schema_version": "phase5.obj3_ann_eval.report.v2",
        "lane": "ann_qdrant_only",
        "fallback_allowed": False,
        "baseline_id": questions.get("baseline_id"),
        "case_count": len(cases),
        "top_k": top_k,
        "embedding_model": settings.embeddings.model_name,
        "embedding_version": settings.embeddings.model_version,
        "embedding_dimension": settings.database.qdrant_vector_size,
        "collection": settings.database.qdrant_collection,
        "scorecard": {
            "recall_at_10": recall,
            "recall_at_10_by_language": by_language,
            "cross_lingual_pair_recall_at_10": round(sum(pair_passes) / len(pair_passes), 3),
            "missing_evidence_cases": [case["case_id"] for case in cases if case["recall_at_10"] < 1.0],
        },
        "latency_ms": {
            "cold_start": latencies[0],
            "steady_p50": _percentile(latencies[1:], 0.50),
            "steady_p95": _percentile(latencies[1:], 0.95),
        },
        "reference": {
            "post_r3_hybrid_recall_at_10": post_r3_hybrid_recall_at_10,
            "direct_comparison_valid": False,
            "reason": "ANN-only recall cannot be gated against a hybrid retrieval score.",
        },
        "acceptance": {
            "ann_baseline_recorded": True,
            "integrity_checks_passed": True,
        },
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    settings = load(ROOT)
    if not settings.embeddings.enabled or not settings.database.qdrant_enabled:
        raise RuntimeError("ANN evaluation requires embeddings and Qdrant to be enabled.")
    client = qdrant.runtime_client(settings)

    def searcher(vector: Sequence[float], top_k: int) -> list[dict[str, Any]]:
        return qdrant.search_chunks(
            client,
            vector,
            top_k=top_k,
            collection=settings.database.qdrant_collection,
        )

    report = run_ann_eval(
        questions=_read_json(args.questions),
        post_r3_hybrid_recall_at_10=float(
            _read_json(args.baseline)["scorecard"]["recall_at_10"]
        ),
        settings=settings,
        searcher=searcher,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["scorecard"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
