"""Cold-start benchmark for a larger vibration corpus.

The script runs S1 ingestion followed by S2/S3/V4 queries and writes a compact
JSON baseline. It is explicit-run tooling, not part of the default test suite.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import Settings, load  # noqa: E402
from vibration_agent.retrieval.hybrid import read_chunks_jsonl  # noqa: E402
from vibration_agent.schemas import SkillInput  # noqa: E402
from vibration_agent.skills import IngestionSkill  # noqa: E402
from vibration_agent.orchestrator import TutorOrchestrator  # noqa: E402
from vibration_agent.storage.qdrant import upsert_chunk_points  # noqa: E402
from vibration_agent.retrieval.embeddings import embed_texts  # noqa: E402


DEFAULT_QUESTIONS: tuple[dict[str, Any], ...] = (
    {"id": "q01", "query": "What happens near critical speed in rotor vibration?", "expected_terms": ["critical speed"]},
    {"id": "q02", "query": "How does damping affect resonance response?", "expected_terms": ["damping"]},
    {"id": "q03", "query": "What does a damping ratio represent in vibration analysis?", "expected_terms": ["damping ratio"]},
    {"id": "q04", "query": "Why is phase important near a rotor critical speed?", "expected_terms": ["phase"]},
    {"id": "q05", "query": "How is unbalance related to rotating machinery vibration?", "expected_terms": ["unbalance"]},
    {"id": "q06", "query": "What does condition monitoring observe in rotor vibration?", "expected_terms": ["condition monitoring"]},
    {"id": "q07", "query": "How can orbit observations support rotor vibration diagnosis?", "expected_terms": ["orbit"]},
    {"id": "q08", "query": "What is the role of frequency response in vibration analysis?", "expected_terms": ["frequency response"]},
    {"id": "q09", "query": "How can resonance peak response be reduced?", "expected_terms": ["resonance"]},
    {"id": "q10", "query": "What measurements are useful when passing through resonance?", "expected_terms": ["resonance"]},
    {"id": "q11", "query": "Why do engineers track vibration amplitude?", "expected_terms": ["amplitude"]},
    {"id": "q12", "query": "How does insufficient damping affect run-up or coast-down?", "expected_terms": ["damping"]},
    {"id": "q13", "query": "What does a vibration spectrum show?", "expected_terms": ["spectrum"]},
    {"id": "q14", "query": "How is bearing vibration relevant to rotating machinery?", "expected_terms": ["bearing"]},
    {"id": "q15", "query": "What is a mode in structural or rotor vibration?", "expected_terms": ["mode"]},
    {"id": "q16", "query": "How are natural frequency and resonance related?", "expected_terms": ["natural frequency"]},
    {"id": "q17", "query": "What is order tracking used for in rotating machinery?", "expected_terms": ["order tracking"]},
    {"id": "q18", "query": "How can misalignment appear in vibration diagnostics?", "expected_terms": ["misalignment"]},
    {"id": "q19", "query": "Why are standards useful in machine vibration evaluation?", "expected_terms": ["standard"]},
    {"id": "q20", "query": "What should a citation identify in an evidence-bound vibration answer?", "expected_terms": ["citation"]},
)


def _load_questions(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return [dict(item) for item in DEFAULT_QUESTIONS]

    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        loaded = json.loads(text)
        rows = loaded.get("questions", loaded) if isinstance(loaded, Mapping) else loaded
    if not isinstance(rows, list):
        raise ValueError("Question file must contain a JSON array, {'questions': [...]}, or JSONL rows.")

    questions: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping) or not str(row.get("query") or "").strip():
            raise ValueError(f"Question row {index} must contain a non-empty query.")
        questions.append(
            {
                "id": str(row.get("id") or f"q{index:02d}"),
                "query": str(row["query"]),
                "expected_terms": [str(term) for term in row.get("expected_terms", [])],
            }
        )
    return questions


def _chunk_paths(s1_result: Mapping[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for document in s1_result.get("documents", []) or []:
        outputs = document.get("outputs", {}) if isinstance(document, Mapping) else {}
        chunks_jsonl = outputs.get("chunks_jsonl") if isinstance(outputs, Mapping) else None
        if chunks_jsonl:
            paths.append(Path(str(chunks_jsonl)))
    return paths


def _read_chunks(paths: Sequence[Path]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for path in paths:
        chunks.extend(read_chunks_jsonl(path))
    return chunks


def _expected_term_hit(text: str, terms: Sequence[str]) -> bool | None:
    expected = [term.casefold() for term in terms if term]
    if not expected:
        return None
    normalized = text.casefold()
    return any(term in normalized for term in expected)


def _retrieval_text(output: Any) -> str:
    s2_result = output.structured_result.get("skill_results", {}).get("s2", {})
    context_rows = s2_result.get("retrieval_context", []) if isinstance(s2_result, Mapping) else []
    if not isinstance(context_rows, list):
        return ""
    return "\n".join(str(row.get("text") or "") for row in context_rows if isinstance(row, Mapping))


def _citation_refs(output: Any) -> list[dict[str, Any]]:
    return [
        {
            "chunk_id": citation.chunk_id,
            "doc_id": citation.doc_id,
            "pages": citation.pages,
            "confidence": citation.confidence,
        }
        for citation in output.citations
    ]


def _maybe_populate_qdrant(
    *,
    settings: Settings,
    chunks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not settings.database.qdrant_enabled:
        return {"enabled": False, "status": "skipped", "reason": "QDRANT_ENABLED is false"}
    texts = [str(chunk.get("text") or chunk.get("api_context") or "") for chunk in chunks]
    records = embed_texts(texts, settings=settings)
    vectors = {
        str(chunk["chunk_id"]): record.vector
        for chunk, record in zip(chunks, records, strict=True)
        if chunk.get("chunk_id") and record.vector and record.provider != "fallback_token_features"
    }
    warnings = list(dict.fromkeys(warning for record in records for warning in record.warnings))
    if not vectors:
        return {
            "enabled": True,
            "status": "skipped",
            "reason": "No real embedding vectors available.",
            "warnings": warnings,
        }
    try:
        from vibration_agent.storage.qdrant import runtime_client

        count = upsert_chunk_points(
            runtime_client(settings),
            chunks,
            embeddings=vectors,
            collection=settings.database.qdrant_collection,
            embedding_model=settings.embeddings.model_name,
            embedding_version=settings.embeddings.model_version,
        )
    except Exception as exc:  # noqa: BLE001 - benchmark should report fallback context
        return {
            "enabled": True,
            "status": "fail",
            "reason": f"{type(exc).__name__}: {exc}",
            "warnings": warnings,
        }
    return {"enabled": True, "status": "ok", "upserted_points": count, "warnings": warnings}


def run_benchmark(
    *,
    corpus: Path,
    workspace: Path,
    output: Path,
    questions: Sequence[Mapping[str, Any]],
    max_pages: int | None = None,
    source_type: str = "book",
    top_k: int = 5,
) -> dict[str, Any]:
    settings = load(workspace)
    started = time.perf_counter()
    ingest_started = time.perf_counter()
    s1_output = IngestionSkill(settings=settings).run(
        SkillInput(
            task_id="obj8-large-corpus-s1",
            user_query="large corpus cold-start ingestion",
            constraints={
                "input_path": str(corpus),
                "max_pages": max_pages,
                "source_type": source_type,
                "write_output": True,
            },
        )
    )
    ingestion_elapsed_ms = int((time.perf_counter() - ingest_started) * 1000)
    chunks_jsonl = _chunk_paths(s1_output.structured_result)
    chunks = _read_chunks(chunks_jsonl)
    qdrant_population = _maybe_populate_qdrant(settings=settings, chunks=chunks)

    query_results: list[dict[str, Any]] = []
    expected_term_checks = 0
    expected_term_hits = 0
    orchestrator = TutorOrchestrator(settings=settings)
    for index, question in enumerate(questions, start=1):
        query = str(question["query"])
        query_started = time.perf_counter()
        answer = orchestrator.handle_query(
            query,
            constraints={"chunk_paths": [str(path) for path in chunks_jsonl], "top_k": top_k, "scope": "in_scope"},
            task_id=f"obj8-q{index:02d}",
        )
        elapsed_ms = int((time.perf_counter() - query_started) * 1000)
        expected_term_hit = _expected_term_hit(_retrieval_text(answer), question.get("expected_terms", []))
        if expected_term_hit is not None:
            expected_term_checks += 1
            expected_term_hits += int(expected_term_hit)
        query_results.append(
            {
                "id": str(question.get("id") or f"q{index:02d}"),
                "query": query,
                "status": answer.status,
                "elapsed_ms": elapsed_ms,
                "citation_count": len(answer.citations),
                "has_citation": bool(answer.citations),
                "citations": _citation_refs(answer),
                "expected_terms": list(question.get("expected_terms", [])),
                "expected_term_hit": expected_term_hit,
                "warnings": answer.warnings,
            }
        )

    no_citation = [item["id"] for item in query_results if not item["has_citation"]]
    total_elapsed_ms = int((time.perf_counter() - started) * 1000)
    baseline = {
        "schema_version": "phase2.obj8.baseline.v1",
        "corpus": str(corpus),
        "workspace": str(settings.paths.workspace),
        "document_count": s1_output.structured_result.get("document_count", 0),
        "chunk_count": s1_output.structured_result.get("chunk_count", len(chunks)),
        "chunks_jsonl": [str(path) for path in chunks_jsonl],
        "elapsed_ms": {
            "ingestion": ingestion_elapsed_ms,
            "total": total_elapsed_ms,
        },
        "question_count": len(query_results),
        "citation_coverage": (len(query_results) - len(no_citation)) / len(query_results) if query_results else 0.0,
        "no_citation_questions": no_citation,
        "expected_term_hit_rate": (expected_term_hits / expected_term_checks) if expected_term_checks else None,
        "expected_term_hit_rate_note": "Proxy metric: checks whether any configured expected term appears in retrieved S2 context text. It is not true retrieval recall.",
        "token_cost": None,
        "runtime": {
            "embedding_provider": settings.embeddings.provider,
            "embedding_model": settings.embeddings.model_name,
            "embedding_local_files_only": settings.embeddings.local_files_only,
            "qdrant_enabled": settings.database.qdrant_enabled,
            "qdrant_population": qdrant_population,
            "postgres_enabled": settings.database.postgres_enabled,
        },
        "s1_status": s1_output.status,
        "s1_warnings": s1_output.warnings,
        "questions": query_results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    return baseline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Obj8 large-corpus cold-start benchmark.")
    parser.add_argument("corpus", type=Path, help="PDF/DOCX file or corpus directory to ingest.")
    parser.add_argument("--workspace", type=Path, default=ROOT, help="Workspace root. Defaults to this repo.")
    parser.add_argument("--questions", type=Path, default=None, help="JSON/JSONL question set. Defaults to 20 sample questions.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "exports" / "large_corpus_baseline.json")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional page cap for smoke runs.")
    parser.add_argument("--source-type", default="book")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--require-qdrant-population",
        action="store_true",
        help="Exit non-zero unless Qdrant cold-start population succeeds.",
    )
    args = parser.parse_args(argv)

    baseline = run_benchmark(
        corpus=args.corpus,
        workspace=args.workspace,
        output=args.output,
        questions=_load_questions(args.questions),
        max_pages=args.max_pages,
        source_type=args.source_type,
        top_k=args.top_k,
    )
    summary = {
        "status": baseline["s1_status"],
        "document_count": baseline["document_count"],
        "chunk_count": baseline["chunk_count"],
        "question_count": baseline["question_count"],
        "citation_coverage": baseline["citation_coverage"],
        "expected_term_hit_rate": baseline["expected_term_hit_rate"],
        "no_citation_questions": baseline["no_citation_questions"],
        "output": str(args.output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.require_qdrant_population and baseline["runtime"]["qdrant_population"].get("status") != "ok":
        return 2
    return 0 if baseline["s1_status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
