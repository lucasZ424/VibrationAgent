"""S3 concept explanation / summary / QA skill.

The default S3 path is deterministic and evidence-bound. Phase-2 Obj9 adds an
explicitly feature-flagged LLM synthesis branch; until V2 citation checking is
active by default, deterministic extraction remains the safe default.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from vibration_agent.agent import ModelRegistry, route_task
from vibration_agent.config import Settings, load
from vibration_agent.knowledge.evidence import citation_from_evidence, retrieval_evidence_row
from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

_SUPPORTED_MODES = {"whole_doc_summary", "section_summary", "qa"}
_DEFAULT_MAX_CLAIMS = {"qa": 4, "section_summary": 5, "whole_doc_summary": 6}
S3Runner = Callable[[list[dict[str, Any]], SkillInput, str, str], tuple[str, list[dict[str, Any]], list[str]]]
S3LlmClient = Any


@dataclass(frozen=True)
class _LlmSynthesis:
    answer: str
    claims: list[dict[str, Any]]
    citations: list[Citation]
    token_cost: int | None
    warnings: list[str]


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


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _llm_enabled(payload: SkillInput, settings: Settings) -> bool:
    value = _first_present(
        payload.constraints,
        payload.context,
        keys=("s3_llm_enabled", "llm_enabled", "use_llm_s3"),
    )
    if value is not None:
        return _as_bool(value, default=False)
    return bool(settings.llm.s3_enabled)


def _role_model(settings: Settings, payload: SkillInput) -> tuple[str, dict[str, Any]]:
    route = route_task(constraints=payload.constraints, context=payload.context, settings=settings)
    registry = ModelRegistry.from_settings(settings)
    # Obj9 keeps S3 on the GPT/main-answer lane. Opus supervisor routing is a
    # later objective and must not be activated from S3 synthesis.
    role = "main_answer"
    if role not in registry.roles:
        role = "interaction_main"
    spec = registry.get(role)
    return spec.ref, {"role": role, **route.model_dump(mode="json")}


def _evidence_prompt(
    *,
    payload: SkillInput,
    rows: list[dict[str, Any]],
    mode: str,
    language: str,
) -> str:
    evidence_blocks = []
    for row in rows:
        evidence_blocks.append(
            "\n".join(
                [
                    f"[{row['chunk_id']}]",
                    f"doc_id: {row['doc_id']}",
                    f"pages: {row.get('pages')}",
                    str(row.get("text") or ""),
                ]
            )
        )
    return "\n\n".join(
        [
            "You are S3 evidence-bound synthesis for a vibration engineering assistant.",
            "Use only the supplied evidence blocks.",
            "Every claim must include a visible [chunk_id] citation from the supplied evidence.",
            "If evidence is insufficient, return insufficient instead of filling gaps.",
            f"mode: {mode}",
            f"language: {language}",
            f"query: {payload.user_query}",
            "evidence:",
            "\n\n".join(evidence_blocks),
        ]
    )


def _call_llm_client(
    client: S3LlmClient,
    *,
    prompt: str,
    model: str,
    rows: list[dict[str, Any]],
    payload: SkillInput,
    mode: str,
    language: str,
    timeout: float,
) -> Any:
    if hasattr(client, "synthesize"):
        return client.synthesize(
            prompt=prompt,
            model=model,
            evidence=rows,
            query=payload.user_query,
            mode=mode,
            language=language,
            timeout=timeout,
        )
    if callable(client):
        return client(
            prompt=prompt,
            model=model,
            evidence=rows,
            query=payload.user_query,
            mode=mode,
            language=language,
            timeout=timeout,
        )
    raise TypeError("S3 LLM client must be callable or expose synthesize().")


def _response_mapping(response: Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if hasattr(response, "model_dump"):
        dumped = response.model_dump(mode="python")
        return dumped if isinstance(dumped, Mapping) else {}
    if isinstance(response, str):
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            return {"answer": response}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def _token_cost(response: Mapping[str, Any]) -> int | None:
    for key in ("token_cost", "total_tokens"):
        value = response.get(key)
        if value not in (None, ""):
            return int(value)
    usage = response.get("token_usage")
    if isinstance(usage, Mapping):
        for key in ("total_tokens", "tokens", "total"):
            value = usage.get(key)
            if value not in (None, ""):
                return int(value)
    return None


def _claim_text(value: Mapping[str, Any]) -> str:
    for key in ("text", "claim", "content"):
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _claim_chunk_id(value: Mapping[str, Any]) -> str | None:
    for key in ("chunk_id", "citation", "source_chunk_id"):
        chunk_id = value.get(key)
        if chunk_id:
            return str(chunk_id).strip("[]")
    citations = value.get("citations")
    if isinstance(citations, list) and citations:
        first = citations[0]
        if isinstance(first, Mapping) and first.get("chunk_id"):
            return str(first["chunk_id"])
        if isinstance(first, str):
            return first.strip("[]")
    return None


def _llm_claims(response: Mapping[str, Any], rows_by_chunk: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    raw_claims = response.get("claims")
    if not isinstance(raw_claims, list):
        return []
    claims: list[dict[str, Any]] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            continue
        text = _claim_text(raw)
        chunk_id = _claim_chunk_id(raw)
        if not text or not chunk_id or chunk_id not in rows_by_chunk:
            continue
        claims.append(
            {
                "text": text,
                "evidence": rows_by_chunk[chunk_id],
                "assets": rows_by_chunk[chunk_id].get("assets", []),
                "score": 1.0,
                "order": (len(claims), 0),
            }
        )
    return claims


def _validate_llm_answer(answer: str, claims: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for claim in claims:
        chunk_id = str(claim["evidence"]["chunk_id"])
        if f"[{chunk_id}]" not in answer:
            warnings.append(f"LLM claim missing visible citation [{chunk_id}].")
    return warnings


def _try_llm_synthesis(
    *,
    client: S3LlmClient | None,
    settings: Settings,
    rows: list[dict[str, Any]],
    payload: SkillInput,
    mode: str,
    language: str,
) -> _LlmSynthesis | None:
    if client is None:
        raise RuntimeError("S3 LLM is enabled but no LLM client is configured.")
    model, route = _role_model(settings, payload)
    prompt = _evidence_prompt(payload=payload, rows=rows, mode=mode, language=language)
    response = _response_mapping(
        _call_llm_client(
            client,
            prompt=prompt,
            model=model,
            rows=rows,
            payload=payload,
            mode=mode,
            language=language,
            timeout=settings.llm.s3_timeout,
        )
    )
    if response.get("status") == "insufficient":
        return None
    answer = str(response.get("answer") or "").strip()
    rows_by_chunk = {str(row["chunk_id"]): row for row in rows}
    claims = _llm_claims(response, rows_by_chunk)
    if not answer or not claims:
        raise RuntimeError("S3 LLM response did not contain cited claims.")
    citation_warnings = _validate_llm_answer(answer, claims)
    if citation_warnings:
        raise RuntimeError("; ".join(citation_warnings))
    warnings = list(response.get("warnings", [])) if isinstance(response.get("warnings"), list) else []
    return _LlmSynthesis(
        answer=answer,
        claims=claims,
        citations=_citations(claims),
        token_cost=_token_cost(response),
        warnings=[*warnings, f"S3 LLM route: {route['role']} -> {model}."],
    )


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

    def __init__(
        self,
        *,
        runner: S3Runner | None = None,
        settings: Settings | None = None,
        llm_client: S3LlmClient | None = None,
    ) -> None:
        self._runner = runner or _default_runner
        self._settings = settings
        self._llm_client = llm_client

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
        active_settings = self._settings or load()
        llm_warnings: list[str] = []
        if _llm_enabled(payload, active_settings):
            try:
                llm = _try_llm_synthesis(
                    client=self._llm_client,
                    settings=active_settings,
                    rows=rows,
                    payload=payload,
                    mode=mode,
                    language=language,
                )
            except Exception as exc:  # noqa: BLE001 - LLM path must degrade to deterministic S3
                llm_warnings.append(
                    f"S3 LLM synthesis unavailable; using deterministic fallback: {type(exc).__name__}: {exc}"
                )
            else:
                if llm is not None:
                    return SkillOutput(
                        status="ok",
                        summary=f"S3 {mode} LLM ok: {len(llm.claims)} claim(s) from {len(llm.citations)} chunk(s).",
                        structured_result={
                            "task_id": payload.task_id,
                            "mode": mode,
                            "language": language,
                            "answer": llm.answer,
                            "claims": [_claim_record(claim) for claim in llm.claims],
                            "assets": _dedupe_assets(llm.claims),
                            "evidence_count": len(rows),
                            "unsupported_claims": [],
                            "synthesis_mode": "llm",
                            "token_cost": llm.token_cost,
                        },
                        citations=llm.citations,
                        warnings=[*evidence_warnings, *llm.warnings],
                        handoff_recommendation="Pass structured_result.answer and citations to V4.",
                    )
                llm_warnings.append("S3 LLM returned insufficient; using deterministic fallback.")

        answer, claims, runner_warnings = self._runner(rows, payload, mode, language)
        warnings = [*evidence_warnings, *llm_warnings, *runner_warnings]

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
                "synthesis_mode": "deterministic",
                "token_cost": None,
            },
            citations=citations,
            warnings=warnings,
            handoff_recommendation="Pass structured_result.answer and citations to V4.",
        )
