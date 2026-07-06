"""Audit Obj7 corpus identity metadata, mojibake, and taxonomy coverage."""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from vibration_agent.config import load  # noqa: E402
from vibration_agent.retrieval.hybrid import load_chunks, load_runtime_chunks  # noqa: E402

DEFAULT_QUESTIONS = ROOT / "tests" / "fixtures" / "rag_qa" / "questions.json"
DEFAULT_TAXONOMY_DIR = ROOT / "taxonomy"
DEFAULT_CHUNKS_DIR = ROOT / "data" / "chunks"
DEFAULT_OUTPUT = ROOT / "run_logs" / "obj7_corpus_audit.json"
REPORT_SCHEMA = "phase5.obj7.corpus_audit.report.v1"
ALIAS_SCHEMA = "phase5.retrieval_aliases.v1"
TEXT_FIELDS = ("text", "api_context", "title", "source_title", "source_filename", "topic")
GENERIC_DOCUMENT_RE = re.compile(r"(^|[/\\])document[_-][a-z0-9]+", re.IGNORECASE)
MOJIBAKE_MARKERS = (
    "�",
    "Ã",
    "Â",
    "â",
    "鈥",
    "锛",
    "锟",
    "鐨",
    "闃",
    "绋",
    "鍥烘",
    "杞",
    "涓€",
    "涓嶅",
    "涓寸",
    "鎸",
    "棰戠",
    "浠€",
    "鍚",
    "鏍囧",
    "绛夎",
    "瑙掑",
    "鐩镐",
    "鍙樺",
    "寮忓",
    "閫傜",
    "妫€",
    "杈冮",
)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return data


def run_obj7_corpus_audit(
    *,
    chunks: Sequence[Mapping[str, Any]],
    questions: Mapping[str, Any],
    taxonomy_dir: Path,
    corpus_source: str = "injected",
    warnings: Sequence[str] = (),
    sample_limit: int = 10,
) -> dict[str, Any]:
    rows = [dict(chunk) for chunk in chunks]
    case_rows = [case for case in questions.get("cases", []) if isinstance(case, Mapping)]
    source_metadata = audit_source_metadata(rows, sample_limit=sample_limit)
    mojibake = audit_mojibake(rows, sample_limit=sample_limit)
    taxonomy = audit_taxonomy(taxonomy_dir, case_rows, sample_limit=sample_limit)
    expected_evidence = audit_expected_evidence(case_rows, sample_limit=sample_limit)
    expected_evidence.update(
        audit_generic_expected_resolution(case_rows, rows, sample_limit=sample_limit)
    )
    unresolved_generic_expected = expected_evidence.get("generic_expected_unresolved_samples", [])
    return {
        "schema_version": REPORT_SCHEMA,
        "question_schema_version": questions.get("schema_version"),
        "corpus": {
            "source": corpus_source,
            "chunk_count": len(rows),
            "doc_count": len({str(chunk.get("doc_id")) for chunk in rows if chunk.get("doc_id")}),
            "source_type_counts": dict(sorted(Counter(str(chunk.get("source_type") or "unknown") for chunk in rows).items())),
            "warnings": list(warnings),
        },
        "source_metadata": source_metadata,
        "mojibake": mojibake,
        "taxonomy": taxonomy,
        "obj1_expected_evidence": expected_evidence,
        "mutation_prerequisites": {
            "audit_completed": True,
            "requires_source_metadata_migration": source_metadata["direct_source_filename_rate"] < 1.0
            or source_metadata["direct_source_title_rate"] < 1.0,
            "requires_mojibake_review": mojibake["chunk_mojibake_count"] > 0
            or taxonomy["retrieval_aliases"].get("mojibake_alias_count", 0) > 0,
            "requires_taxonomy_review": bool(taxonomy["key_fact_alias_coverage"]["missing_alias_samples"]),
            "requires_generic_document_review": source_metadata["generic_user_facing_identity_count"] > 0
            or bool(unresolved_generic_expected),
        },
    }


def audit_source_metadata(chunks: Sequence[Mapping[str, Any]], *, sample_limit: int) -> dict[str, Any]:
    total = len(chunks)
    direct_filename = 0
    direct_title = 0
    fallback_filename = 0
    fallback_title = 0
    stable_path = 0
    generic_samples: list[dict[str, Any]] = []
    generic_user_facing_samples: list[dict[str, Any]] = []
    generic_internal_samples: list[dict[str, Any]] = []
    missing_filename: list[dict[str, Any]] = []
    missing_title: list[dict[str, Any]] = []
    missing_path: list[dict[str, Any]] = []
    for chunk in chunks:
        if _has_text(chunk.get("source_filename")):
            direct_filename += 1
        if _has_text(chunk.get("source_title")):
            direct_title += 1
        resolved_filename = _resolved_source_filename(chunk)
        resolved_title = _resolved_source_title(chunk)
        resolved_path = _resolved_source_path(chunk)
        if resolved_filename:
            fallback_filename += 1
        elif len(missing_filename) < sample_limit:
            missing_filename.append(_chunk_sample(chunk))
        if resolved_title:
            fallback_title += 1
        elif len(missing_title) < sample_limit:
            missing_title.append(_chunk_sample(chunk))
        if resolved_path:
            stable_path += 1
        elif len(missing_path) < sample_limit:
            missing_path.append(_chunk_sample(chunk))
        if _has_generic_identity(chunk) and len(generic_samples) < sample_limit:
            generic_samples.append(_chunk_sample(chunk))
        if _has_generic_user_facing_identity(chunk) and len(generic_user_facing_samples) < sample_limit:
            generic_user_facing_samples.append(_chunk_sample(chunk))
        if _has_generic_internal_identity(chunk) and len(generic_internal_samples) < sample_limit:
            generic_internal_samples.append(_chunk_sample(chunk))
    generic_user_facing_count = sum(1 for chunk in chunks if _has_generic_user_facing_identity(chunk))
    generic_internal_count = sum(1 for chunk in chunks if _has_generic_internal_identity(chunk))
    return {
        "direct_source_filename_count": direct_filename,
        "direct_source_filename_rate": _rate(direct_filename, total),
        "direct_source_title_count": direct_title,
        "direct_source_title_rate": _rate(direct_title, total),
        "fallback_source_filename_count": fallback_filename,
        "fallback_source_filename_rate": _rate(fallback_filename, total),
        "fallback_source_title_count": fallback_title,
        "fallback_source_title_rate": _rate(fallback_title, total),
        "stable_source_path_count": stable_path,
        "stable_source_path_rate": _rate(stable_path, total),
        "generic_identity_count": sum(1 for chunk in chunks if _has_generic_identity(chunk)),
        "generic_user_facing_identity_count": generic_user_facing_count,
        "generic_internal_identity_count": generic_internal_count,
        "generic_identity_samples": generic_samples,
        "generic_user_facing_identity_samples": generic_user_facing_samples,
        "generic_internal_identity_samples": generic_internal_samples,
        "missing_source_filename_samples": missing_filename,
        "missing_source_title_samples": missing_title,
        "missing_source_path_samples": missing_path,
    }


def audit_mojibake(chunks: Sequence[Mapping[str, Any]], *, sample_limit: int) -> dict[str, Any]:
    field_counts: Counter[str] = Counter()
    chunk_ids: set[str] = set()
    samples: list[dict[str, Any]] = []
    for chunk in chunks:
        for field in TEXT_FIELDS:
            value = chunk.get(field)
            if not isinstance(value, str) or not looks_mojibake(value):
                continue
            field_counts[field] += 1
            if chunk.get("chunk_id"):
                chunk_ids.add(str(chunk["chunk_id"]))
            if len(samples) < sample_limit:
                samples.append({**_chunk_sample(chunk), "field": field, "excerpt": _excerpt(value)})
    return {
        "scanned_fields": list(TEXT_FIELDS),
        "chunk_mojibake_count": len(chunk_ids),
        "chunk_mojibake_rate": _rate(len(chunk_ids), len(chunks)),
        "field_counts": dict(sorted(field_counts.items())),
        "samples": samples,
    }


def audit_taxonomy(taxonomy_dir: Path, cases: Sequence[Mapping[str, Any]], *, sample_limit: int) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    aliases: list[dict[str, str]] = []
    case_ids = {str(case.get("case_id") or "") for case in cases if case.get("case_id")}
    retrieval_summary: dict[str, Any] = {
        "schema_version": None,
        "family_count": 0,
        "alias_count": 0,
        "mojibake_alias_count": 0,
        "families_with_mojibake_aliases": [],
        "traceable_family_count": 0,
        "trace_metadata_issue_samples": [],
    }
    for path in sorted(taxonomy_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            files.append({"path": _rel(path), "parse_ok": False, "error": f"{type(exc).__name__}: {exc}"})
            continue
        files.append(_yaml_file_summary(path, data))
        if path.name != "retrieval_aliases.yaml" or not isinstance(data, Mapping):
            continue
        families = data.get("families") if isinstance(data.get("families"), list) else []
        families_with_mojibake: list[str] = []
        traceable_family_count = 0
        trace_issues: list[dict[str, Any]] = []
        for family in families:
            if not isinstance(family, Mapping):
                continue
            family_id = str(family.get("id") or "")
            family_aliases = family.get("aliases") if isinstance(family.get("aliases"), list) else []
            family_has_mojibake = False
            for alias in family_aliases:
                alias_text = str(alias).strip()
                if not alias_text:
                    continue
                aliases.append({"family_id": family_id, "alias": alias_text})
                family_has_mojibake = family_has_mojibake or looks_mojibake(alias_text)
            if family_has_mojibake:
                families_with_mojibake.append(family_id)
            if family.get("source_miss_case_ids"):
                traceable_family_count += 1
                issues = _trace_metadata_issues(family, case_ids)
                if issues and len(trace_issues) < sample_limit:
                    trace_issues.append({"family_id": family_id, "issues": issues})
        retrieval_summary = {
            "schema_version": data.get("schema_version"),
            "family_count": len(families),
            "alias_count": len(aliases),
            "mojibake_alias_count": sum(1 for item in aliases if looks_mojibake(item["alias"])),
            "families_with_mojibake_aliases": families_with_mojibake[:sample_limit],
            "traceable_family_count": traceable_family_count,
            "trace_metadata_issue_samples": trace_issues,
        }
    return {
        "files": files,
        "retrieval_aliases": retrieval_summary,
        "key_fact_alias_coverage": _key_fact_alias_coverage(cases, aliases, sample_limit=sample_limit),
    }


def _trace_metadata_issues(family: Mapping[str, Any], case_ids: set[str]) -> list[str]:
    issues: list[str] = []
    if not _has_text(family.get("canonical")):
        issues.append("missing_canonical")
    if not isinstance(family.get("languages"), list) or not family.get("languages"):
        issues.append("missing_languages")
    if not _has_text(family.get("ambiguity")):
        issues.append("missing_ambiguity")
    source_ids = family.get("source_miss_case_ids")
    if not isinstance(source_ids, list) or not source_ids:
        issues.append("missing_source_miss_case_ids")
        return issues
    unknown = [str(case_id) for case_id in source_ids if str(case_id) not in case_ids]
    if unknown:
        issues.append("unknown_source_miss_case_ids:" + ",".join(unknown[:3]))
    return issues


def audit_expected_evidence(cases: Sequence[Mapping[str, Any]], *, sample_limit: int) -> dict[str, Any]:
    doc_ids: set[str] = set()
    chunk_ids: set[str] = set()
    generic_docs: set[str] = set()
    generic_chunks: list[dict[str, str]] = []
    for case in cases:
        for item in case.get("expected_evidence", []) or []:
            if not isinstance(item, Mapping):
                continue
            doc_id = str(item.get("doc_id") or "")
            chunk_id = str(item.get("chunk_id") or "")
            if doc_id:
                doc_ids.add(doc_id)
            if chunk_id:
                chunk_ids.add(chunk_id)
            if _is_generic(doc_id):
                generic_docs.add(doc_id)
            if (_is_generic(doc_id) or _is_generic(chunk_id)) and len(generic_chunks) < sample_limit:
                generic_chunks.append({"case_id": str(case.get("case_id") or ""), "doc_id": doc_id, "chunk_id": chunk_id})
    return {
        "expected_doc_count": len(doc_ids),
        "expected_chunk_count": len(chunk_ids),
        "generic_expected_doc_ids": sorted(generic_docs),
        "generic_expected_evidence_samples": generic_chunks,
    }


def audit_generic_expected_resolution(
    cases: Sequence[Mapping[str, Any]],
    chunks: Sequence[Mapping[str, Any]],
    *,
    sample_limit: int,
) -> dict[str, Any]:
    by_chunk_id = {str(chunk.get("chunk_id")): chunk for chunk in chunks if chunk.get("chunk_id")}
    by_doc_id: dict[str, Mapping[str, Any]] = {}
    for chunk in chunks:
        if chunk.get("doc_id"):
            by_doc_id.setdefault(str(chunk["doc_id"]), chunk)
    resolved = 0
    unresolved: list[dict[str, str | None]] = []
    for case in cases:
        for item in case.get("expected_evidence", []) or []:
            if not isinstance(item, Mapping):
                continue
            doc_id = str(item.get("doc_id") or "")
            chunk_id = str(item.get("chunk_id") or "")
            if not (_is_generic(doc_id) or _is_generic(chunk_id)):
                continue
            chunk = by_chunk_id.get(chunk_id) or by_doc_id.get(doc_id)
            if chunk and _has_real_user_facing_identity(chunk):
                resolved += 1
                continue
            if len(unresolved) < sample_limit:
                unresolved.append(
                    {
                        "case_id": str(case.get("case_id") or ""),
                        "doc_id": doc_id or None,
                        "chunk_id": chunk_id or None,
                    }
                )
    return {
        "generic_expected_resolved_count": resolved,
        "generic_expected_unresolved_samples": unresolved,
    }


def looks_mojibake(text: str) -> bool:
    if not text:
        return False
    if "\ufffd" in text:
        return True
    compact = text.strip()
    if compact in MOJIBAKE_MARKERS:
        return True
    marker_hits = sum(text.count(marker) for marker in MOJIBAKE_MARKERS)
    if "�" in text or "锟" in text:
        return True
    if marker_hits >= 3:
        return True
    return marker_hits >= 2 and marker_hits / max(len(text), 1) >= 0.01


def _yaml_file_summary(path: Path, data: Any) -> dict[str, Any]:
    if isinstance(data, Mapping):
        size = len(data)
        kind = "mapping"
    elif isinstance(data, list):
        size = len(data)
        kind = "list"
    else:
        size = 0
        kind = type(data).__name__
    return {"path": _rel(path), "parse_ok": True, "kind": kind, "top_level_count": size}


def _key_fact_alias_coverage(
    cases: Sequence[Mapping[str, Any]],
    aliases: Sequence[Mapping[str, str]],
    *,
    sample_limit: int,
) -> dict[str, Any]:
    alias_set = {_normalize_alias(item["alias"]) for item in aliases if item.get("alias")}
    total = 0
    covered = 0
    missing: list[dict[str, str]] = []
    for case in cases:
        for fact in case.get("key_facts", []) or []:
            if not isinstance(fact, Mapping):
                continue
            for alias in fact.get("aliases", []) or []:
                alias_text = str(alias).strip()
                if not alias_text:
                    continue
                total += 1
                if _normalize_alias(alias_text) in alias_set:
                    covered += 1
                elif len(missing) < sample_limit:
                    missing.append(
                        {
                            "case_id": str(case.get("case_id") or ""),
                            "fact_id": str(fact.get("fact_id") or ""),
                            "alias": alias_text,
                        }
                    )
    return {
        "key_fact_alias_count": total,
        "covered_alias_count": covered,
        "covered_alias_rate": _rate(covered, total),
        "missing_alias_count": max(total - covered, 0),
        "missing_alias_samples": missing,
    }


def _normalize_alias(value: str) -> str:
    return " ".join(value.casefold().split())


def _metadata(chunk: Mapping[str, Any]) -> Mapping[str, Any]:
    metadata = chunk.get("metadata")
    return metadata if isinstance(metadata, Mapping) else {}


def _first_text(*values: Any) -> str | None:
    for value in values:
        if _has_text(value):
            return str(value).strip()
    return None


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _basename(value: Any) -> str | None:
    text = _first_text(value)
    if text is None:
        return None
    return text.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1] or None


def _resolved_source_filename(chunk: Mapping[str, Any]) -> str | None:
    metadata = _metadata(chunk)
    return _first_text(
        chunk.get("source_filename"),
        chunk.get("input_filename"),
        chunk.get("filename"),
        metadata.get("source_filename"),
        metadata.get("input_filename"),
        metadata.get("filename"),
    ) or _basename(chunk.get("source_path")) or _basename(metadata.get("source_path"))


def _resolved_source_title(chunk: Mapping[str, Any]) -> str | None:
    metadata = _metadata(chunk)
    return _first_text(chunk.get("source_title"), chunk.get("title"), metadata.get("source_title"), metadata.get("title"))


def _resolved_source_path(chunk: Mapping[str, Any]) -> str | None:
    metadata = _metadata(chunk)
    return _first_text(chunk.get("source_path"), metadata.get("source_path"))


def _has_generic_identity(chunk: Mapping[str, Any]) -> bool:
    metadata = _metadata(chunk)
    values = (
        chunk.get("doc_id"),
        chunk.get("chunk_id"),
        chunk.get("source_filename"),
        chunk.get("source_title"),
        chunk.get("source_path"),
        chunk.get("title"),
        metadata.get("source_filename"),
        metadata.get("source_title"),
        metadata.get("source_path"),
        metadata.get("title"),
    )
    return any(_is_generic(value) for value in values if value is not None)


def _has_generic_user_facing_identity(chunk: Mapping[str, Any]) -> bool:
    metadata = _metadata(chunk)
    values = (
        chunk.get("source_filename"),
        chunk.get("source_title"),
        chunk.get("source_path"),
        chunk.get("title"),
        metadata.get("source_filename"),
        metadata.get("source_title"),
        metadata.get("source_path"),
        metadata.get("title"),
    )
    return any(_is_generic(value) for value in values if value is not None)


def _has_real_user_facing_identity(chunk: Mapping[str, Any]) -> bool:
    filename = _resolved_source_filename(chunk)
    title = _resolved_source_title(chunk)
    return bool(filename and title and not _is_generic(filename) and not _is_generic(title))


def _has_generic_internal_identity(chunk: Mapping[str, Any]) -> bool:
    return _is_generic(chunk.get("doc_id")) or _is_generic(chunk.get("chunk_id"))


def _is_generic(value: Any) -> bool:
    return bool(GENERIC_DOCUMENT_RE.search(str(value)))


def _chunk_sample(chunk: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "doc_id": chunk.get("doc_id"),
        "source_filename": _resolved_source_filename(chunk),
        "source_title": _resolved_source_title(chunk),
        "source_path": _resolved_source_path(chunk),
    }


def _excerpt(text: str, limit: int = 180) -> str:
    compact = " ".join(text.split())
    marker_positions = [compact.find(marker) for marker in MOJIBAKE_MARKERS if compact.find(marker) >= 0]
    if not marker_positions:
        return compact[:limit]
    center = min(marker_positions)
    start = max(center - limit // 3, 0)
    return compact[start : start + limit]


def _rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_corpus(args: argparse.Namespace) -> tuple[list[dict[str, Any]], str, list[str]]:
    warnings: list[str] = []
    if args.source == "runtime":
        settings = load(ROOT)
        chunks = load_runtime_chunks(settings)
        if not chunks:
            raise RuntimeError("Runtime Qdrant corpus is unavailable or empty.")
        return chunks, "runtime_qdrant", warnings
    chunk_paths = args.chunk_path or []
    chunks_dir = args.chunks_dir
    if chunks_dir is None and not chunk_paths and args.source in {"auto", "chunks"}:
        chunks_dir = DEFAULT_CHUNKS_DIR
    if args.source == "auto":
        try:
            settings = load(ROOT)
            chunks = load_runtime_chunks(settings)
            if chunks:
                return chunks, "runtime_qdrant", warnings
            warnings.append("Runtime Qdrant corpus returned no chunks; falling back to file chunks.")
        except Exception as exc:
            warnings.append(f"Runtime Qdrant corpus unavailable: {type(exc).__name__}: {exc}")
    chunks = load_chunks(chunk_paths=chunk_paths, chunks_dir=chunks_dir)
    if not chunks:
        raise RuntimeError("No chunk corpus available for Obj7 audit.")
    return chunks, "file_chunks", warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--taxonomy-dir", type=Path, default=DEFAULT_TAXONOMY_DIR)
    parser.add_argument("--chunks-dir", type=Path)
    parser.add_argument("--chunk-path", type=Path, action="append")
    parser.add_argument("--source", choices=("auto", "runtime", "chunks"), default="auto")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args(argv)
    chunks, corpus_source, warnings = _load_corpus(args)
    report = run_obj7_corpus_audit(
        chunks=chunks,
        questions=read_json(args.questions),
        taxonomy_dir=args.taxonomy_dir,
        corpus_source=corpus_source,
        warnings=warnings,
        sample_limit=args.sample_limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "corpus": report["corpus"],
                "source_metadata": {
                    "direct_source_filename_rate": report["source_metadata"]["direct_source_filename_rate"],
                    "direct_source_title_rate": report["source_metadata"]["direct_source_title_rate"],
                    "fallback_source_filename_rate": report["source_metadata"]["fallback_source_filename_rate"],
                    "fallback_source_title_rate": report["source_metadata"]["fallback_source_title_rate"],
                    "generic_identity_count": report["source_metadata"]["generic_identity_count"],
                },
                "mojibake": {
                    "chunk_mojibake_count": report["mojibake"]["chunk_mojibake_count"],
                    "field_counts": report["mojibake"]["field_counts"],
                },
                "taxonomy": {
                    "retrieval_aliases": report["taxonomy"]["retrieval_aliases"],
                    "missing_key_fact_aliases": report["taxonomy"]["key_fact_alias_coverage"]["missing_alias_count"],
                },
                "mutation_prerequisites": report["mutation_prerequisites"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
