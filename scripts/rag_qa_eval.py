"""Phase-5 Obj1 real-question RAG baseline evaluator.

The evaluator runs the existing S2 -> S3 -> V2 -> V4 chain. It never creates
an LLM client; tests inject a deterministic query runner and the CLI uses the
deterministic TutorOrchestrator path against the local corpus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.orchestrator.tutor import TutorOrchestrator  # noqa: E402
from vibration_agent.retrieval.hybrid import load_runtime_chunks  # noqa: E402
from vibration_agent.schemas import SkillOutput  # noqa: E402
from vibration_agent.skills.s2_retrieval import RetrievalSkill  # noqa: E402

DEFAULT_QUESTIONS = ROOT / "tests" / "fixtures" / "rag_qa" / "questions.json"
DEFAULT_BASELINE = ROOT / "tests" / "fixtures" / "rag_qa" / "post_r3_baseline.json"
REQUIRED_INTENTS = {
    "definition",
    "mechanism",
    "comparison",
    "diagnosis",
    "workflow",
    "standards",
    "formula",
}
REQUIRED_LANGUAGES = {"zh", "en"}
MISS_PRIORITY = (
    "corpus-quality",
    "terminology",
    "retrieval",
    "ranking",
    "cross-doc",
    "synthesis",
    "pass",
)
QueryRunner = Callable[[Mapping[str, Any]], SkillOutput]


def load_questions(path: Path = DEFAULT_QUESTIONS) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError(f"{path} must contain an object with a cases array.")
    _validate_questions(data)
    return data


def _validate_questions(data: Mapping[str, Any]) -> None:
    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) < 14:
        raise ValueError("Obj1 requires at least 14 labeled cases.")
    ids: set[str] = set()
    coverage: set[tuple[str, str]] = set()
    for row in cases:
        if not isinstance(row, Mapping):
            raise ValueError("Every case must be an object.")
        case_id = str(row.get("case_id") or "")
        if not case_id or case_id in ids:
            raise ValueError(f"Case ids must be non-empty and unique: {case_id!r}.")
        ids.add(case_id)
        intent, language = str(row.get("intent") or ""), str(row.get("language") or "")
        coverage.add((intent, language))
        if not row.get("query") or not row.get("expected_evidence") or not row.get("key_facts"):
            raise ValueError(f"{case_id} requires query, expected_evidence, and key_facts.")
        rubric = row.get("completeness_rubric")
        boundary = row.get("evidence_boundary")
        if (
            not isinstance(rubric, Mapping)
            or not rubric.get("required_sections")
            or not rubric.get("human_usable_if")
        ):
            raise ValueError(f"{case_id} requires a human completeness rubric.")
        if not isinstance(boundary, Mapping) or not boundary.get("allowed_doc_ids"):
            raise ValueError(f"{case_id} requires an evidence boundary.")
    missing = {(intent, language) for intent in REQUIRED_INTENTS for language in REQUIRED_LANGUAGES} - coverage
    if missing:
        raise ValueError(f"Obj1 intent/language coverage is incomplete: {sorted(missing)}")


def make_local_runner(*, settings: Settings, chunks: Sequence[Mapping[str, Any]]) -> QueryRunner:
    orchestrator = TutorOrchestrator(
        settings=settings,
        retrieval_skill=RetrievalSkill(settings=settings),
    )

    def run(case: Mapping[str, Any]) -> SkillOutput:
        return orchestrator.handle_query(
            str(case["query"]),
            task_id=str(case["case_id"]),
            user_mode="engineering",
            context={"chunks": list(chunks)},
            constraints={
                "top_k": 10,
                "difficulty": "low",
                "s3_llm_enabled": False,
                "llm_enabled": False,
                "advisory_routing_enabled": False,
            },
        )

    return run


def run_rag_qa_eval(
    *,
    questions: Mapping[str, Any] | None = None,
    query_runner: QueryRunner,
    corpus_count: int | None = None,
    git_commit: str | None = None,
) -> dict[str, Any]:
    active = dict(questions or load_questions())
    _validate_questions(active)
    cases = [_run_case(row, query_runner=query_runner) for row in active["cases"]]
    _apply_paired_terminology(cases, active["cases"])
    primary_counts = Counter(case["miss_category"] for case in cases)
    signal_counts = Counter(signal for case in cases for signal in case["miss_categories"])
    failure_counts = Counter({key: value for key, value in signal_counts.items() if key != "pass"})
    dominant = failure_counts.most_common(1)[0] if failure_counts else ("none", 0)
    v2_status_counts = Counter(case["v2_status"] for case in cases)
    deterministic = [_deterministic_case(case) for case in cases]
    report = {
        "schema_version": "phase5.rag_qa.report.v2",
        "question_schema_version": active.get("schema_version"),
        "baseline_id": active.get("baseline_id"),
        "corpus": {**dict(active.get("corpus") or {}), "actual_chunk_count": corpus_count},
        "retrieval_config": dict(active.get("retrieval_config") or {}),
        "evaluation_contract": {
            "evidence_match_rule": "exact_chunk_id OR same_doc_id_with_page_overlap",
            "miss_counts_are_multi_label": True,
            "terminology_rule": (
                "paired zh/en cases over identical labeled evidence with asymmetric recall@10"
            ),
        },
        "git_commit": git_commit or _git_commit(),
        "live_providers_constructed": False,
        "case_count": len(cases),
        "scorecard": {
            "recall_at_5": _mean(cases, "recall_at_5"),
            "recall_at_10": _mean(cases, "recall_at_10"),
            "completeness_rate": _mean(cases, "completeness"),
            "v2_faithfulness_rate": round(
                sum(case["v2_status"] == "ok" for case in cases) / len(cases), 3
            ),
            "sentence_completeness_rate": _mean(cases, "sentence_completeness"),
            "latency_ms": {
                "total": round(sum(case["latency_ms"] for case in cases), 3),
                "mean": round(sum(case["latency_ms"] for case in cases) / len(cases), 3),
                "max": round(max(case["latency_ms"] for case in cases), 3),
            },
            "v2_status_counts": dict(sorted(v2_status_counts.items())),
            "miss_counts": dict(sorted(signal_counts.items())),
            "primary_miss_counts": dict(sorted(primary_counts.items())),
            "dominant_miss_category": {"category": dominant[0], "count": dominant[1]},
        },
        "deterministic_fingerprint": hashlib.sha256(
            json.dumps(deterministic, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "cases": cases,
    }
    return report


def _run_case(case: Mapping[str, Any], *, query_runner: QueryRunner) -> dict[str, Any]:
    started = time.perf_counter()
    output = query_runner(case)
    latency_ms = (time.perf_counter() - started) * 1000
    structured = output.structured_result if isinstance(output.structured_result, Mapping) else {}
    skills = structured.get("skill_results") if isinstance(structured.get("skill_results"), Mapping) else {}
    s2 = skills.get("s2") if isinstance(skills.get("s2"), Mapping) else {}
    retrieval = s2.get("retrieval_output") if isinstance(s2.get("retrieval_output"), Mapping) else {}
    hits = [dict(hit) for hit in retrieval.get("hits", []) if isinstance(hit, Mapping)]
    answer = str(structured.get("answer") or output.summary or "")
    matched_5 = _matched_evidence(case, hits[:5])
    matched_10 = _matched_evidence(case, hits[:10])
    expected_count = len(case["expected_evidence"])
    facts = _fact_results(case, answer)
    sections = set(_section_keys(skills))
    required_sections = set(case["completeness_rubric"]["required_sections"])
    section_score = len(sections & required_sections) / len(required_sections)
    fact_score = sum(item["covered"] for item in facts) / len(facts)
    completeness = round((section_score + fact_score) / 2, 3)
    quality = structured.get("answer_quality") if isinstance(structured.get("answer_quality"), Mapping) else {}
    subscores = quality.get("subscores") if isinstance(quality.get("subscores"), Mapping) else {}
    v2_status = str(quality.get("faithfulness_status") or "unknown")
    citations = [citation.model_dump(mode="json") for citation in output.citations]
    boundary = case["evidence_boundary"]
    allowed_docs = set(boundary["allowed_doc_ids"])
    boundary_ok = all(str(citation.get("doc_id")) in allowed_docs for citation in citations)
    result = {
        "case_id": case["case_id"],
        "intent": case["intent"],
        "language": case["language"],
        "query": case["query"],
        "status": output.status,
        "retrieval_source": structured.get("retrieval_source") or s2.get("retrieval_source"),
        "retrieval_hits": hits,
        "matched_evidence_at_5": matched_5,
        "matched_evidence_at_10": matched_10,
        "recall_at_5": round(len(matched_5) / expected_count, 3),
        "recall_at_10": round(len(matched_10) / expected_count, 3),
        "answer": answer,
        "citations": citations,
        "v2_status": v2_status,
        "fact_results": facts,
        "completeness": completeness,
        "sentence_completeness": round(float(subscores.get("readability") or 0.0), 3),
        "evidence_boundary_ok": boundary_ok,
        "latency_ms": round(latency_ms, 3),
        "warnings": list(output.warnings),
    }
    result["miss_categories"] = _miss_categories(case, result)
    result["miss_category"] = _primary_miss(result["miss_categories"])
    return result


def _matched_evidence(case: Mapping[str, Any], hits: Sequence[Mapping[str, Any]]) -> list[str]:
    matched: list[str] = []
    for target in case["expected_evidence"]:
        target_pages = set(target.get("pages") or [])
        for hit in hits:
            exact = target.get("chunk_id") and str(hit.get("chunk_id")) == str(target["chunk_id"])
            same_page = str(hit.get("doc_id")) == str(target.get("doc_id")) and bool(
                target_pages & set(hit.get("pages") or [])
            )
            if exact or same_page:
                matched.append(str(target["evidence_id"]))
                break
    return matched


def _fact_results(case: Mapping[str, Any], answer: str) -> list[dict[str, Any]]:
    folded = " ".join(answer.casefold().split())
    return [
        {
            "fact_id": fact["fact_id"],
            "covered": any(" ".join(str(alias).casefold().split()) in folded for alias in fact["aliases"]),
        }
        for fact in case["key_facts"]
    ]


def _section_keys(skills: Mapping[str, Any]) -> list[str]:
    v4 = skills.get("v4")
    return list(v4.get("section_keys") or []) if isinstance(v4, Mapping) else []


def _miss_categories(case: Mapping[str, Any], result: Mapping[str, Any]) -> list[str]:
    risks = set(case.get("diagnostic_hints") or [])
    categories: list[str] = []
    if result["recall_at_10"] < 1:
        if "corpus-quality" in risks:
            categories.append("corpus-quality")
        else:
            categories.append("retrieval")
    if result["recall_at_5"] < result["recall_at_10"]:
        categories.append("ranking")
    if case["evidence_boundary"].get("requires_multiple_docs") and result["completeness"] < 1:
        categories.append("cross-doc")
    if result["completeness"] < 1 or result["v2_status"] != "ok" or not result["evidence_boundary_ok"]:
        categories.append("synthesis")
    return categories or ["pass"]


def _apply_paired_terminology(cases: list[dict[str, Any]], definitions: Sequence[Mapping[str, Any]]) -> None:
    definition_by_id = {str(row["case_id"]): row for row in definitions}
    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for case in cases:
        definition = definition_by_id[str(case["case_id"])]
        evidence_ids = tuple(sorted(str(item["evidence_id"]) for item in definition["expected_evidence"]))
        groups.setdefault((str(definition["intent"]), evidence_ids), []).append(case)
    for paired_cases in groups.values():
        by_language = {str(case["language"]): case for case in paired_cases}
        if set(by_language) != REQUIRED_LANGUAGES:
            continue
        for language, peer_language in (("zh", "en"), ("en", "zh")):
            case, peer = by_language[language], by_language[peer_language]
            if case["recall_at_10"] < 1 and peer["recall_at_10"] == 1:
                case["miss_categories"] = [
                    "terminology" if category == "retrieval" else category
                    for category in case["miss_categories"]
                ]
                case["miss_category"] = _primary_miss(case["miss_categories"])


def _primary_miss(categories: Sequence[str]) -> str:
    return next(category for category in MISS_PRIORITY if category in categories)


def _deterministic_case(case: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in case.items() if key != "latency_ms"}


def _mean(cases: Sequence[Mapping[str, Any]], key: str) -> float:
    return round(sum(float(case[key]) for case in cases) / len(cases), 3)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _offline_settings(settings: Settings) -> Settings:
    model_path = Path(settings.embeddings.model_name).expanduser()
    if not model_path.exists():
        cache_root = Path(
            os.getenv("HUGGINGFACE_HUB_CACHE")
            or (
                Path(os.getenv("HF_HOME")) / "hub"
                if os.getenv("HF_HOME")
                else Path.home() / ".cache" / "huggingface" / "hub"
            )
        )
        model_dir = (
            cache_root
            / f"models--{settings.embeddings.model_name.replace('/', '--')}"
            / "snapshots"
        )
        snapshots = sorted(path for path in model_dir.glob("*") if path.is_dir())
        if not snapshots:
            raise RuntimeError(f"Offline embedding snapshot not found for {settings.embeddings.model_name}.")
        model_path = snapshots[-1]
    return settings.model_copy(
        update={
            "database": settings.database.model_copy(update={"postgres_enabled": False}),
            "embeddings": settings.embeddings.model_copy(
                update={"model_name": str(model_path), "local_files_only": True}
            ),
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the Phase-5 Obj1 real-question RAG baseline."
    )
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_BASELINE)
    args = parser.parse_args(argv)
    settings = _offline_settings(load(ROOT))
    chunks = load_runtime_chunks(settings)
    if not chunks:
        raise SystemExit("Local Qdrant corpus is unavailable or empty; baseline was not written.")
    local_runner = make_local_runner(settings=settings, chunks=chunks)

    def reporting_runner(case: Mapping[str, Any]) -> SkillOutput:
        print(f"running {case['case_id']}...", file=sys.stderr, flush=True)
        return local_runner(case)

    report = run_rag_qa_eval(
        questions=load_questions(args.questions),
        query_runner=reporting_runner,
        corpus_count=len(chunks),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["scorecard"], ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
