"""S3 concept explanation / summary / QA skill.

Phase-0 S3 is deterministic and evidence-bound. It does not call an LLM or use
model-world knowledge to fill gaps; it extracts concise cited sentence selections
from S2 evidence. Synthesized prose is deferred until LLM integration lands.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

from vibration_agent.knowledge.evidence import citation_from_evidence, retrieval_evidence_row
from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

_SUPPORTED_MODES = {"whole_doc_summary", "section_summary", "qa"}
_DEFAULT_MAX_CLAIMS = {"qa": 4, "section_summary": 5, "whole_doc_summary": 6}
S3Runner = Callable[[list[dict[str, Any]], SkillInput, str, str], tuple[str, list[dict[str, Any]], list[str]]]


def _first_present(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _mode(payload: SkillInput) -> str:
    value = _first_present(payload.constraints, payload.context, keys=("mode", "task", "summary_mode"))
    if value in _SUPPORTED_MODES:
        return str(value)
    query = payload.user_query.lower()
    if any(marker in query for marker in ("whole doc", "whole document", "整本", "全文", "全书")):
        return "whole_doc_summary"
    if any(marker in query for marker in ("section", "章节", "小节", "本节")):
        return "section_summary"
    return "qa"


def _s2_context(payload: SkillInput) -> tuple[list[Any], bool]:
    candidates: list[Any] = []
    saw_hits_without_text = False
    if payload.retrieval_results:
        candidates.extend(payload.retrieval_results)
        saw_hits_without_text = True
    for key in ("retrieval_context", "evidence", "chunks"):
        value = payload.context.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    s2_result = payload.context.get("s2_result")
    if isinstance(s2_result, Mapping):
        structured = s2_result.get("structured_result") if isinstance(s2_result.get("structured_result"), Mapping) else s2_result
        value = structured.get("retrieval_context") if isinstance(structured, Mapping) else None
        if isinstance(value, list):
            candidates.extend(value)
        retrieval_output = structured.get("retrieval_output") if isinstance(structured, Mapping) else None
        hits = retrieval_output.get("hits") if isinstance(retrieval_output, Mapping) else None
        if isinstance(hits, list):
            candidates.extend(hits)
            saw_hits_without_text = True
    return candidates, saw_hits_without_text


def _citation_confidence_by_chunk(payload: SkillInput) -> dict[str, float]:
    values: dict[str, float] = {}
    for item in payload.context.get("citations", []) if isinstance(payload.context.get("citations"), list) else []:
        if isinstance(item, Mapping) and item.get("chunk_id") and item.get("confidence") is not None:
            values[str(item["chunk_id"])] = float(item["confidence"])
    s2_result = payload.context.get("s2_result")
    if isinstance(s2_result, Mapping):
        citations = s2_result.get("citations")
        if isinstance(citations, list):
            for item in citations:
                if isinstance(item, Mapping) and item.get("chunk_id") and item.get("confidence") is not None:
                    values[str(item["chunk_id"])] = float(item["confidence"])
    return values


def _evidence_rows(payload: SkillInput) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()
    dropped = 0
    candidates, saw_hits_without_text = _s2_context(payload)
    confidence_by_chunk = _citation_confidence_by_chunk(payload)
    for item in candidates:
        if not isinstance(item, Mapping):
            dropped += 1
            continue
        row = retrieval_evidence_row(item)
        if row is None or not row.get("text"):
            dropped += 1
            continue
        key = str(row["chunk_id"])
        if key in seen:
            continue
        if key in confidence_by_chunk:
            row["confidence"] = confidence_by_chunk[key]
        seen.add(key)
        rows.append(row)
    if dropped:
        warnings.append(f"S3 dropped {dropped} retrieval row(s) without usable chunk text.")
    if saw_hits_without_text and not rows:
        warnings.append("S3 received retrieval hits without text; pass retrieval_context from S2.")
    return rows, warnings


def _normalize_topic(value: Any) -> str:
    return re.sub(r"[_\W]+", " ", str(value or "").lower()).strip()


def _filter_evidence(rows: list[dict[str, Any]], payload: SkillInput, mode: str) -> list[dict[str, Any]]:
    doc_id = _first_present(payload.constraints, payload.context, keys=("doc_id",))
    section_id = _first_present(payload.constraints, payload.context, keys=("section_id", "section_key"))
    topic = _first_present(payload.constraints, payload.context, keys=("topic",))
    filtered = rows
    if doc_id:
        filtered = [row for row in filtered if str(row.get("doc_id")) == str(doc_id)]
    if mode == "section_summary" and section_id:
        filtered = [
            row
            for row in filtered
            if str(row.get("metadata", {}).get("section_key")) == str(section_id)
            or str(row.get("metadata", {}).get("section_id")) == str(section_id)
        ]
    if mode == "section_summary" and topic:
        expected = _normalize_topic(topic)
        filtered = [
            row
            for row in filtered
            if expected in _normalize_topic(row.get("topic")) or _normalize_topic(row.get("topic")) in expected
        ]
    return filtered


def _body_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[") and "]\n" in stripped:
        return stripped.split("]\n", 1)[1].strip()
    return stripped


def _sentences(text: str) -> list[str]:
    body = _body_text(text)
    parts = re.split(r"(?<=[。！？!?；;\.])\s*|\n+", body)
    cleaned = [re.sub(r"\s+", " ", part).strip() for part in parts]
    return [part for part in cleaned if len(part) >= 2]


def _language_hint(row: Mapping[str, Any]) -> str | None:
    for key in ("language", "doc_language", "source_language"):
        value = row.get(key)
        if value in {"zh", "en"}:
            return str(value)
    metadata = row.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("language", "doc_language", "source_language"):
            value = metadata.get(key)
            if value in {"zh", "en"}:
                return str(value)
    return None


def _dominant_language(rows: list[Mapping[str, Any]]) -> str:
    hints = [_language_hint(row) for row in rows]
    if hints.count("zh") > hints.count("en"):
        return "zh"
    if hints.count("en") > hints.count("zh"):
        return "en"
    text = "\n".join(_body_text(str(row.get("text") or "")) for row in rows)
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    return "zh" if cjk >= latin else "en"


def _citation_label(row: Mapping[str, Any]) -> str:
    return str(row["chunk_id"])


def _max_claims(payload: SkillInput, mode: str) -> int:
    value = _first_present(payload.constraints, payload.context, keys=("max_claims",))
    if value in (None, ""):
        return _DEFAULT_MAX_CLAIMS[mode]
    return int(value)


def _ranked_claims(rows: list[dict[str, Any]], query: str, *, limit: int) -> list[dict[str, Any]]:
    query_tokens = set(tokenize(query))
    candidates: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        for sentence_index, sentence in enumerate(_sentences(str(row.get("text") or ""))):
            sentence_tokens = set(tokenize(sentence))
            overlap = len(query_tokens & sentence_tokens) if query_tokens else 0
            score = overlap * 10 + max(0.0, float(row.get("confidence") or 0.0))
            if query_tokens and overlap == 0:
                score = max(0.0, float(row.get("confidence") or 0.0)) * 0.1
            candidates.append(
                {
                    "text": sentence,
                    "evidence": row,
                    "assets": row.get("assets", []),
                    "score": score,
                    "order": (row_index, sentence_index),
                }
            )
    candidates.sort(key=lambda item: (-float(item["score"]), item["order"]))
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate["text"].lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected


def _claims_to_answer(claims: list[dict[str, Any]], *, language: str, prefix: str) -> str:
    lines = [prefix]
    for index, claim in enumerate(claims, start=1):
        label = _citation_label(claim["evidence"])
        if language == "zh":
            lines.append(f"{index}. {claim['text']}（证据：{label}）")
        else:
            lines.append(f"{index}. {claim['text']} (evidence: {label})")
    return "\n".join(lines)


def _qa(rows: list[dict[str, Any]], payload: SkillInput, language: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    claims = _ranked_claims(rows, payload.user_query, limit=_max_claims(payload, "qa"))
    if not claims:
        return "", [], ["Retrieved evidence contains no usable text claims."]
    prefix = "根据已检索证据，可以确定：" if language == "zh" else "Based on the retrieved evidence:"
    return _claims_to_answer(claims, language=language, prefix=prefix), claims, []


def _whole_doc_summary(rows: list[dict[str, Any]], payload: SkillInput, language: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("doc_id"))].append(row)
    selected: list[dict[str, Any]] = []
    for doc_rows in grouped.values():
        selected.extend(_ranked_claims(doc_rows, payload.user_query or "summary", limit=2))
    selected.sort(key=lambda item: (-float(item["score"]), item["order"]))
    selected = selected[: _max_claims(payload, "whole_doc_summary")]
    if not selected:
        return "", [], ["Retrieved evidence contains no usable text for document summary."]
    prefix = "文档摘要：" if language == "zh" else "Document summary:"
    return _claims_to_answer(selected, language=language, prefix=prefix), selected, []


def _section_summary(rows: list[dict[str, Any]], payload: SkillInput, language: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    selected = _ranked_claims(rows, payload.user_query or "section summary", limit=_max_claims(payload, "section_summary"))
    if not selected:
        return "", [], ["Retrieved evidence contains no usable text for section summary."]
    prefix = "本节要点：" if language == "zh" else "Section takeaways:"
    return _claims_to_answer(selected, language=language, prefix=prefix), selected, []


def _default_runner(rows: list[dict[str, Any]], payload: SkillInput, mode: str, language: str) -> tuple[str, list[dict[str, Any]], list[str]]:
    if mode == "whole_doc_summary":
        return _whole_doc_summary(rows, payload, language)
    if mode == "section_summary":
        return _section_summary(rows, payload, language)
    return _qa(rows, payload, language)


def _citations(claims: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for claim in claims:
        citation = citation_from_evidence(claim["evidence"])
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        citations.append(citation)
    return citations


def _claim_record(claim: Mapping[str, Any]) -> dict[str, Any]:
    evidence = claim["evidence"]
    assets = claim.get("assets", []) if isinstance(claim.get("assets"), list) else []
    return {
        "text": claim["text"],
        "chunk_id": evidence["chunk_id"],
        "doc_id": evidence["doc_id"],
        "pages": evidence.get("pages"),
        "evidence_type": "documented",
        "assets": assets,
        "asset_ids": [asset.get("asset_id") for asset in assets if isinstance(asset, Mapping) and asset.get("asset_id")],
    }


def _dedupe_assets(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets_by_id: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    for claim in claims:
        for asset in claim.get("assets", []) or []:
            if not isinstance(asset, Mapping):
                continue
            asset_dict = dict(asset)
            asset_id = asset_dict.get("asset_id")
            if asset_id:
                assets_by_id[str(asset_id)] = asset_dict
            else:
                anonymous.append(asset_dict)
    return [*assets_by_id.values(), *anonymous]


class QASummarySkill(Skill):
    name = "s3_qa_summary"

    def __init__(self, *, runner: S3Runner | None = None) -> None:
        self._runner = runner or _default_runner

    def run(self, payload: SkillInput) -> SkillOutput:
        mode = _mode(payload)
        rows, evidence_warnings = _evidence_rows(payload)
        rows = _filter_evidence(rows, payload, mode)
        if not rows:
            return SkillOutput(
                status="insufficient",
                summary="S3 requires retrieved evidence with chunk text.",
                structured_result={"task_id": payload.task_id, "mode": mode, "evidence_count": 0},
                warnings=[*evidence_warnings, "No usable retrieval evidence supplied to S3."],
                handoff_recommendation="Run S2 retrieval first and pass retrieval_context to S3.",
            )

        language = _dominant_language(rows)
        answer, claims, runner_warnings = self._runner(rows, payload, mode, language)
        warnings = [*evidence_warnings, *runner_warnings]

        if not claims:
            return SkillOutput(
                status="insufficient",
                summary="S3 could not produce cited claims from retrieved evidence.",
                structured_result={"task_id": payload.task_id, "mode": mode, "evidence_count": len(rows)},
                warnings=warnings or ["No cited claims produced."],
                handoff_recommendation="Broaden retrieval or inspect S2 results.",
            )

        citations = _citations(claims)
        return SkillOutput(
            status="ok",
            summary=f"S3 {mode} ok: {len(claims)} claim(s) from {len(citations)} chunk(s).",
            structured_result={
                "task_id": payload.task_id,
                "mode": mode,
                "language": language,
                "answer": answer,
                "claims": [_claim_record(claim) for claim in claims],
                "assets": _dedupe_assets(claims),
                "evidence_count": len(rows),
                "unsupported_claims": [],
            },
            citations=citations,
            warnings=warnings,
            handoff_recommendation="Pass structured_result.answer and citations to V4.",
        )
