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
from vibration_agent.retrieval.query_normalize import focus_aliases, is_standard_scope_query
from vibration_agent.schemas import Citation, S3LlmClaim, S3LlmResponse, SkillInput, SkillOutput
from vibration_agent.text import dominant_language

from .base import Skill

_SUPPORTED_MODES = {"whole_doc_summary", "section_summary", "qa"}
_DEFAULT_MAX_CLAIMS = {"qa": 4, "section_summary": 5, "whole_doc_summary": 6}
_PROMPT_VERSION = "s3_qa_summary.v1"
_SCHEMA_VERSION = "s3.v1"
S3Runner = Callable[[list[dict[str, Any]], SkillInput, str, str], tuple[str, list[dict[str, Any]], list[str]]]
S3LlmClient = Any


@dataclass(frozen=True)
class _LlmSynthesis:
    answer: str
    claims: list[dict[str, Any]]
    citations: list[Citation]
    token_cost: int | None
    cost: dict[str, Any] | None
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
    for key in ("retrieval_context", "evidence"):
        value = payload.context.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    s2_result = payload.context.get("s2_result")
    if isinstance(s2_result, Mapping):
        structured = s2_result.get("structured_result") if isinstance(s2_result.get("structured_result"), Mapping) else s2_result
        value = structured.get("evidence_context") if isinstance(structured, Mapping) else None
        if not isinstance(value, list):
            value = structured.get("retrieval_context") if isinstance(structured, Mapping) else None
        has_retrieval_context = isinstance(value, list) and bool(value)
        if isinstance(value, list):
            candidates.extend(value)
        retrieval_output = structured.get("retrieval_output") if isinstance(structured, Mapping) else None
        hits = retrieval_output.get("hits") if isinstance(retrieval_output, Mapping) else None
        if isinstance(hits, list) and not has_retrieval_context:
            candidates.extend(hits)
            saw_hits_without_text = True
    if not candidates:
        value = payload.context.get("chunks")
        if isinstance(value, list):
            candidates.extend(value)
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
    filtered = [
        row
        for row in filtered
        if not re.search(
            r"^(?:参考文献|references|bibliography)$",
            str(row.get("metadata", {}).get("section_title") or row.get("topic") or "").strip(),
            re.IGNORECASE,
        )
    ]
    return filtered


def _body_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("[") and "]\n" in stripped:
        return stripped.split("]\n", 1)[1].strip()
    return stripped


_FINAL_PUNCTUATION_RE = re.compile(r"[。！？!?；;…\.．][\"'”’）】》]*$")
_SECTION_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)+$")
_STRUCTURAL_LINE_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\s+\S|第.+[章节条部分](?:\s|$)|[（(]\d+[)）]|[-•·]\s+|"
    r"[A-Z][A-Z0-9 _./:-]{2,}$|.{0,30}(?:概述|样本)$|.*\d{2,}[A-Z]\d+.*修订版|"
    r"[^。！？!?；;]{1,40}[•·][^。！？!?；;]{1,40}$|\[\d+\]\s*\S+)"
)
_PAGE_NUMBER_RE = re.compile(r"^\d{1,4}$")
_CROSS_CHUNK_ORPHAN_RE = re.compile(r"^司[A-Z]")
_CJK_ASSERTION_MARKERS = ("是", "为", "表示", "用于", "产生", "影响", "规定", "提供", "支持", "增大", "减小")
_SCOPE_CLAIM_MARKERS = (
    "适用",
    "本文件规定",
    "本标准规定",
    "本部分规定",
    "applies to",
    "applicable to",
    "scope of",
    "this document specifies",
    "this standard specifies",
)
_CRITICAL_SPEED_OUTCOME_QUERY_MARKERS = (
    "发生什么",
    "会怎样",
    "如何变化",
    "影响",
    "what happens",
    "affect",
    "effect",
)
_CRITICAL_SPEED_TERMS = ("临界转速", "临界速度", "critical speed", "resonant speed", "共振转速")
_CRITICAL_SPEED_OUTCOME_CLAIM_MARKERS = (
    "响应",
    "振幅",
    "幅值",
    "放大",
    "增大",
    "amplified",
    "amplification",
    "response",
    "amplitude",
)
_DEFINITION_ONLY_MARKERS = ("定义", "definition")


def _explicit_structural_line(line: str) -> bool:
    stripped = line.strip()
    short_cjk_label = bool(
        len(stripped) <= 16
        and not _FINAL_PUNCTUATION_RE.search(stripped)
        and sum("\u4e00" <= char <= "\u9fff" for char in stripped) >= max(2, len(stripped) // 2)
        and not any(marker in stripped for marker in _CJK_ASSERTION_MARKERS)
    )
    return bool(
        _SECTION_NUMBER_RE.fullmatch(stripped)
        or _STRUCTURAL_LINE_RE.match(stripped)
        or _PAGE_NUMBER_RE.fullmatch(stripped)
        or short_cjk_label
    )


def _join_soft_wrap(left: str, right: str) -> str:
    if left.endswith("-") and right[:1].isascii() and right[:1].isalpha():
        return left[:-1] + right
    left_char = left[-1:] or ""
    right_char = right[:1] or ""
    if left_char.isascii() and left_char.isalnum() and right_char.isascii() and right_char.isalnum():
        return left + " " + right
    return left + right


def _line_units(text: str) -> list[tuple[str, bool]]:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    structural = [_explicit_structural_line(line) for line in lines]
    for index in range(1, len(lines)):
        if _SECTION_NUMBER_RE.fullmatch(lines[index - 1]):
            structural[index] = True
        if lines[index] == lines[index - 1]:
            structural[index - 1] = True
            structural[index] = True

    units: list[tuple[str, bool]] = [(lines[0], structural[0])]
    for index in range(1, len(lines)):
        previous_line = lines[index - 1]
        line = lines[index]
        hard_boundary = bool(
            _FINAL_PUNCTUATION_RE.search(previous_line)
            or structural[index - 1]
            or structural[index]
        )
        if hard_boundary:
            units.append((line, structural[index]))
        else:
            current, is_structural = units[-1]
            units[-1] = (_join_soft_wrap(current, line), is_structural)
    return units


def _soft_layout_continuation(left: str, right: str) -> bool:
    return bool(
        not _FINAL_PUNCTUATION_RE.search(left)
        and (
            len(left) >= 18
            or re.match(r"^[\u4e00-\u9fff]{1,2}[，、；：。]", right)
        )
    )


def _reflow_units(text: str) -> list[tuple[str, bool]]:
    units: list[tuple[str, bool]] = []
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph_units = _line_units(paragraph)
        if not paragraph_units:
            continue
        if (
            units
            and not units[-1][1]
            and not paragraph_units[0][1]
            and _soft_layout_continuation(units[-1][0], paragraph_units[0][0])
        ):
            left, _ = units[-1]
            right, _ = paragraph_units.pop(0)
            units[-1] = (_join_soft_wrap(left, right), False)
        units.extend(paragraph_units)
    return units


def _reflow(text: str) -> str:
    return "\n".join(value for value, _is_structural in _reflow_units(text))


def _sentences(text: str) -> list[str]:
    parts: list[str] = []
    for block, is_structural in _reflow_units(_body_text(text)):
        if is_structural:
            continue
        parts.extend(re.split(r"(?<=[。！？!?；;…．])\s*|(?<=\.)\s+", block))
    cleaned = [re.sub(r"\s+", " ", part).strip() for part in parts]
    return [part for part in cleaned if len(part) >= 2 and not _CROSS_CHUNK_ORPHAN_RE.match(part)]


def _row_sentences(row: Mapping[str, Any]) -> list[str]:
    metadata = row.get("metadata") if isinstance(row.get("metadata"), Mapping) else {}
    segments = metadata.get("text_segments") if isinstance(metadata, Mapping) else None
    if not isinstance(segments, list):
        return _sentences(str(row.get("text") or ""))

    source_text = _body_text(str(row.get("text") or ""))
    body_segments: list[str] = []
    for segment in segments:
        if (
            not isinstance(segment, Mapping)
            or segment.get("block_type") == "title"
            or segment.get("layout_role") in {"label", "bibliography"}
        ):
            continue
        text = str(segment.get("text") or "")
        if not text and isinstance(segment.get("start"), int) and isinstance(segment.get("end"), int):
            start = int(segment["start"])
            end = int(segment["end"])
            if 0 <= start <= end <= len(source_text):
                text = source_text[start:end]
        text = text.strip()
        if text:
            body_segments.append(text)
    return _sentences("\n\n".join(body_segments))


def _is_scope_claim(text: str) -> bool:
    lowered = text.lower()
    return (
        any(marker in lowered for marker in _SCOPE_CLAIM_MARKERS)
        and "引用文件" not in text
        and "适用于本文件" not in text
    )


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
                    f"evidence_type: {row.get('evidence_type', 'documented')}",
                    str(row.get("text") or ""),
                ]
            )
        )
    return "\n\n".join(
        [
            "You are S3 evidence-bound synthesis for a vibration engineering assistant.",
            "Use only the supplied evidence blocks.",
            "Return JSON only. Do not include markdown fences.",
            "Schema: {\"status\":\"ok|insufficient\",\"answer\":\"...\",\"claims\":[{\"text\":\"...\",\"chunk_id\":\"...\",\"doc_id\":\"...\",\"pages\":[1],\"evidence_type\":\"documented\"}],\"warnings\":[]}",
            "Every claim must include text, chunk_id, doc_id, pages, and evidence_type.",
            "Every claim must cite a visible [chunk_id] from the supplied evidence in the answer.",
            "Use only chunk_id values present in the supplied evidence blocks.",
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
    provider_settings: Any,
) -> Any:
    kwargs = {
        "prompt": prompt,
        "model": model,
        "prompt_version": _PROMPT_VERSION,
        "schema_version": _SCHEMA_VERSION,
        "max_tokens": int(provider_settings.max_tokens),
        "reasoning_effort": provider_settings.reasoning_effort,
        "text_verbosity": provider_settings.text_verbosity,
        "evidence": rows,
        "query": payload.user_query,
        "mode": mode,
        "language": language,
        "timeout": timeout,
        "task_id": payload.task_id,
    }
    if hasattr(client, "synthesize"):
        return client.synthesize(**kwargs)
    if callable(client):
        return client(**kwargs)
    raise TypeError("S3 LLM client must be callable or expose synthesize().")


def _provider_settings(settings: Settings, model: str) -> Any:
    provider = model.split(":", 1)[0] if ":" in model else settings.llm.openai.provider
    if provider == "anthropic":
        return settings.llm.anthropic
    return settings.llm.openai


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


def _llm_response(response: Mapping[str, Any]) -> S3LlmResponse:
    return S3LlmResponse.model_validate(response)


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
    usage = response.get("usage")
    if isinstance(usage, Mapping):
        for key in ("total_tokens", "tokens", "total"):
            value = usage.get(key)
            if value not in (None, ""):
                return int(value)
    return None


def _cost(response: Mapping[str, Any]) -> dict[str, Any] | None:
    value = response.get("cost")
    return dict(value) if isinstance(value, Mapping) else None


def _fallback_evidence(claim: S3LlmClaim) -> dict[str, Any]:
    return {
        "evidence_kind": "text",
        "chunk_id": claim.chunk_id,
        "doc_id": claim.doc_id,
        "pages": claim.pages,
        "text": "",
        "evidence_type": claim.evidence_type,
        "confidence": 1.0,
        "metadata": {"s3_llm_visible_evidence": False},
        "assets": [],
    }


def _llm_claims(response: S3LlmResponse, rows_by_chunk: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for raw in response.claims:
        evidence = rows_by_chunk.get(raw.chunk_id) or _fallback_evidence(raw)
        claims.append(
            {
                "text": raw.text,
                "evidence": evidence,
                "assets": evidence.get("assets", []),
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
    provider_settings = _provider_settings(settings, model)
    prompt = _evidence_prompt(payload=payload, rows=rows, mode=mode, language=language)
    raw_response = _response_mapping(
        _call_llm_client(
            client,
            prompt=prompt,
            model=model,
            rows=rows,
            payload=payload,
            mode=mode,
            language=language,
            timeout=settings.llm.s3_timeout,
            provider_settings=provider_settings,
        )
    )
    if raw_response.get("refusal"):
        raise RuntimeError("S3 LLM refused the request.")
    response = _llm_response(raw_response)
    if response.status == "insufficient":
        return None
    if response.status in {"refusal", "refused"}:
        raise RuntimeError("S3 LLM refused the request.")
    answer = response.answer.strip()
    rows_by_chunk = {str(row["chunk_id"]): row for row in rows}
    claims = _llm_claims(response, rows_by_chunk)
    if not answer or not claims:
        raise RuntimeError("S3 LLM response did not contain cited claims.")
    citation_warnings = _validate_llm_answer(answer, claims)
    if citation_warnings:
        raise RuntimeError("; ".join(citation_warnings))
    warnings = list(response.warnings)
    return _LlmSynthesis(
        answer=answer,
        claims=claims,
        citations=_citations(claims),
        token_cost=_token_cost(raw_response),
        cost=_cost(raw_response),
        warnings=[*warnings, f"S3 LLM route: {route['role']} -> {model}."],
    )


def _ranked_claims(rows: list[dict[str, Any]], query: str, *, limit: int) -> list[dict[str, Any]]:
    query_tokens = set(tokenize(query))
    candidates: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows):
        for sentence_index, sentence in enumerate(_row_sentences(row)):
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
    focus = focus_aliases(query)
    if focus:
        focused_candidates = [
            candidate
            for candidate in candidates
            if any(alias.casefold() in candidate["text"].casefold() for alias in focus)
        ]
        if focused_candidates:
            candidates = focused_candidates
    if is_standard_scope_query(query):
        scope_candidates = [candidate for candidate in candidates if _is_scope_claim(candidate["text"])]
        if scope_candidates:
            candidates = scope_candidates
    if _is_critical_speed_outcome_query(query):
        outcome_candidates = [
            candidate
            for candidate in candidates
            if _is_critical_speed_outcome_claim(candidate["text"])
        ]
        if outcome_candidates:
            candidates = outcome_candidates
        else:
            return []
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


def _contains_casefold(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker.casefold() in lowered for marker in markers)


def _is_critical_speed_outcome_query(query: str) -> bool:
    return _contains_casefold(query, _CRITICAL_SPEED_TERMS) and _contains_casefold(
        query, _CRITICAL_SPEED_OUTCOME_QUERY_MARKERS
    )


def _is_critical_speed_outcome_claim(text: str) -> bool:
    if _contains_casefold(text, _DEFINITION_ONLY_MARKERS):
        return False
    return _contains_casefold(text, _CRITICAL_SPEED_TERMS) and _contains_casefold(
        text, _CRITICAL_SPEED_OUTCOME_CLAIM_MARKERS
    )


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
        if _is_critical_speed_outcome_query(payload.user_query):
            return "", [], ["Retrieved evidence does not contain critical-speed outcome evidence."]
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
        metadata = claim["evidence"].get("metadata")
        if isinstance(metadata, Mapping) and metadata.get("s3_llm_visible_evidence") is False:
            continue
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
        "source_filename": evidence.get("source_filename"),
        "source_title": evidence.get("source_title"),
        "evidence_type": evidence.get("evidence_type") or "documented",
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


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


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

        language = "zh" if _has_cjk(payload.user_query) else dominant_language(rows)
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
                            "cost": llm.cost,
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
