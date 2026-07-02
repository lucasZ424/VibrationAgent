"""S4 engineering analysis.

S4 is optional and runs after S3 when the user asks in engineering mode. It
adds engineering framing from existing cited claims, then hands the result to V2
so citation visibility remains enforced.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vibration_agent.agent import ModelRegistry, route_task
from vibration_agent.config import Settings, load
from vibration_agent.schemas import Citation, S3LlmClaim, S4LlmResponse, SkillInput, SkillOutput
from vibration_agent.text import dominant_language

from .base import Skill

_PROMPT_VERSION = "s4_engineering_analysis.v1"
_SCHEMA_VERSION = "s4.v1"
S4LlmClient = Any


@dataclass(frozen=True)
class _LlmAnalysis:
    answer: str
    engineering_meaning: str
    premises: str
    failure_modes: str
    next_action: str
    claims: list[dict[str, Any]]
    citations: list[Citation]
    token_cost: int | None
    cost: dict[str, Any] | None
    warnings: list[str]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, SkillOutput):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    return {}


def _source_output(payload: SkillInput) -> Mapping[str, Any]:
    for key in ("s3_result", "upstream_result", "skill_output"):
        source = _as_mapping(payload.context.get(key))
        if source:
            return source
    return payload.context


def _structured(source: Mapping[str, Any]) -> Mapping[str, Any]:
    structured = source.get("structured_result")
    return structured if isinstance(structured, Mapping) else source


def _claims(structured: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = structured.get("claims")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping) and item.get("text") and item.get("chunk_id")]


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _first_present(*mappings: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value not in (None, ""):
                return value
    return None


def _llm_enabled(payload: SkillInput, settings: Settings) -> bool:
    value = _first_present(
        payload.constraints,
        payload.context,
        keys=("s4_llm_enabled", "llm_enabled", "use_llm_s4"),
    )
    if value is not None:
        return _as_bool(value, default=False)
    return bool(settings.llm.s4_enabled)


def _s2_visible_rows(payload: SkillInput) -> Mapping[str, Mapping[str, Any]]:
    s2_result = _as_mapping(payload.context.get("s2_result"))
    structured = s2_result.get("structured_result")
    s2_structured = structured if isinstance(structured, Mapping) else s2_result
    rows: dict[str, Mapping[str, Any]] = {}
    retrieval_context = s2_structured.get("evidence_context")
    if not isinstance(retrieval_context, list):
        retrieval_context = s2_structured.get("retrieval_context")
    if isinstance(retrieval_context, list):
        for row in retrieval_context:
            if isinstance(row, Mapping) and row.get("chunk_id"):
                rows[str(row["chunk_id"])] = row
    return rows


def _source_citations(source: Mapping[str, Any], claims: list[Mapping[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    raw = source.get("citations")
    if isinstance(raw, list):
        for item in raw:
            try:
                citation = item if isinstance(item, Citation) else Citation.model_validate(item)
            except Exception:
                continue
            if citation.chunk_id not in seen:
                seen.add(citation.chunk_id)
                citations.append(citation)
    for claim in claims:
        chunk_id = str(claim.get("chunk_id") or "")
        doc_id = str(claim.get("doc_id") or "")
        if chunk_id and doc_id and chunk_id not in seen:
            citations.append(
                Citation(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    pages=claim.get("pages") if isinstance(claim.get("pages"), list) else None,
                )
            )
            seen.add(chunk_id)
    return citations


def _visible_citations(source: Mapping[str, Any], claims: list[Mapping[str, Any]], visible_rows: Mapping[str, Mapping[str, Any]]) -> list[Citation]:
    visible_claims = [claim for claim in claims if str(claim.get("chunk_id") or "") in visible_rows]
    return _source_citations(source, visible_claims)


def _role_model(settings: Settings, payload: SkillInput) -> tuple[str, dict[str, Any]]:
    route = route_task(constraints=payload.constraints, context=payload.context, settings=settings)
    registry = ModelRegistry.from_settings(settings)
    role = "main_answer"
    if role not in registry.roles:
        role = "interaction_main"
    spec = registry.get(role)
    return spec.ref, {"role": role, **route.model_dump(mode="json")}


def _provider_settings(settings: Settings, model: str) -> Any:
    provider = model.split(":", 1)[0] if ":" in model else settings.llm.openai.provider
    if provider == "anthropic":
        return settings.llm.anthropic
    return settings.llm.openai


def _evidence_prompt(
    *,
    payload: SkillInput,
    claims: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
    answer: str,
) -> str:
    blocks: list[str] = []
    for claim in claims:
        chunk_id = str(claim["chunk_id"])
        row = visible_rows[chunk_id]
        blocks.append(
            "\n".join(
                [
                    f"[{chunk_id}]",
                    f"doc_id: {claim.get('doc_id') or row.get('doc_id')}",
                    f"pages: {claim.get('pages') or row.get('pages')}",
                    f"s3_claim: {claim['text']}",
                    f"evidence: {row.get('text') or row.get('api_context') or ''}",
                ]
            )
        )
    return "\n\n".join(
        [
            "You are S4 engineering analysis for a vibration engineering assistant.",
            "Use only the supplied S3 claims and visible S2 evidence.",
            "Return JSON only. Do not include markdown fences.",
            "Schema: {\"status\":\"ok|insufficient\",\"answer\":\"...\",\"engineering_meaning\":\"...\",\"premises\":\"...\",\"failure_modes\":\"...\",\"next_action\":\"...\",\"claims\":[{\"text\":\"...\",\"chunk_id\":\"...\",\"doc_id\":\"...\",\"pages\":[1],\"evidence_type\":\"documented\"}],\"warnings\":[]}",
            "Every engineering judgment must be represented in claims[] and must cite a visible [chunk_id] in answer.",
            "Do not invent numeric thresholds, units, operating conditions, maintenance actions, or failure modes.",
            f"query: {payload.user_query}",
            f"s3_answer: {answer}",
            "evidence:",
            "\n\n".join(blocks),
        ]
    )


def _call_llm_client(
    client: S4LlmClient,
    *,
    prompt: str,
    model: str,
    payload: SkillInput,
    claims: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
    answer: str,
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
        "claims": claims,
        "evidence": [dict(visible_rows[str(claim["chunk_id"])]) for claim in claims],
        "s3_answer": answer,
        "query": payload.user_query,
        "mode": "engineering_analysis",
        "timeout": provider_settings.timeout,
        "task_id": payload.task_id,
    }
    if hasattr(client, "analyze_engineering"):
        return client.analyze_engineering(**kwargs)
    if callable(client):
        return client(**kwargs)
    raise TypeError("S4 LLM client must be callable or expose analyze_engineering().")


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
    for usage_key in ("token_usage", "usage"):
        usage = response.get(usage_key)
        if isinstance(usage, Mapping):
            for key in ("total_tokens", "tokens", "total"):
                value = usage.get(key)
                if value not in (None, ""):
                    return int(value)
    return None


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _cost(response: Mapping[str, Any]) -> dict[str, Any] | None:
    value = response.get("cost")
    return dict(value) if isinstance(value, Mapping) else None


def _claim_record(claim: S3LlmClaim) -> dict[str, Any]:
    return claim.model_dump(mode="json")


def _try_llm_analysis(
    *,
    client: S4LlmClient | None,
    settings: Settings,
    payload: SkillInput,
    claims: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
    answer: str,
    source: Mapping[str, Any],
) -> _LlmAnalysis | None:
    if client is None:
        raise RuntimeError("S4 LLM is enabled but no LLM client is configured.")
    model, route = _role_model(settings, payload)
    provider_settings = _provider_settings(settings, model)
    prompt = _evidence_prompt(payload=payload, claims=claims, visible_rows=visible_rows, answer=answer)
    raw_response = _response_mapping(
        _call_llm_client(
            client,
            prompt=prompt,
            model=model,
            payload=payload,
            claims=claims,
            visible_rows=visible_rows,
            answer=answer,
            provider_settings=provider_settings,
        )
    )
    if raw_response.get("refusal"):
        raise RuntimeError("S4 LLM refused the request.")
    response = S4LlmResponse.model_validate(raw_response)
    if response.status == "insufficient":
        return None
    if response.status in {"refusal", "refused"}:
        raise RuntimeError("S4 LLM refused the request.")
    required_sections = {
        "answer": response.answer,
        "engineering_meaning": response.engineering_meaning,
        "premises": response.premises,
        "failure_modes": response.failure_modes,
        "next_action": response.next_action,
    }
    missing_sections = [key for key, value in required_sections.items() if not value.strip()]
    if missing_sections:
        raise RuntimeError("S4 LLM response missing required engineering fields: " + ", ".join(missing_sections))
    if not response.claims:
        raise RuntimeError("S4 LLM response did not contain cited engineering claims.")
    claim_records = [_claim_record(claim) for claim in response.claims]
    return _LlmAnalysis(
        answer=response.answer.strip(),
        engineering_meaning=response.engineering_meaning.strip(),
        premises=response.premises.strip(),
        failure_modes=response.failure_modes.strip(),
        next_action=response.next_action.strip(),
        claims=claim_records,
        citations=_visible_citations(source, claim_records, visible_rows),
        token_cost=_token_cost(raw_response),
        cost=_cost(raw_response),
        warnings=[*response.warnings, f"S4 LLM route: {route['role']} -> {model}."],
    )


class EngineeringAnalysisSkill(Skill):
    name = "s4_engineering_analysis"

    def __init__(self, *, settings: Settings | None = None, llm_client: S4LlmClient | None = None) -> None:
        self._settings = settings
        self._llm_client = llm_client

    def run(self, payload: SkillInput) -> SkillOutput:
        if payload.user_mode != "engineering":
            return SkillOutput(
                status="insufficient",
                summary="S4 skipped: engineering analysis requires user_mode='engineering'.",
                structured_result={"task_id": payload.task_id, "skip_reason": "user_mode"},
                handoff_recommendation="Use user_mode='engineering' to request S4 engineering analysis.",
            )

        source = _source_output(payload)
        structured = _structured(source)
        visible_rows = _s2_visible_rows(payload)
        claims = [claim for claim in _claims(structured) if str(claim.get("chunk_id")) in visible_rows]
        if not claims:
            return SkillOutput(
                status="insufficient",
                summary="S4 skipped: engineering analysis requires cited S3 claims visible to S2.",
                structured_result={"task_id": payload.task_id, "skip_reason": "insufficient_evidence"},
                warnings=["S4 found no cited claims tied to visible retrieval evidence."],
                handoff_recommendation="Run S2/S3 with enough cited evidence before S4.",
            )

        first_claim = str(claims[0]["text"]).strip()
        chunk_ids = list(dict.fromkeys(str(claim["chunk_id"]) for claim in claims))
        answer = str(structured.get("answer") or source.get("summary") or first_claim).strip()
        language = str(
            structured.get("language")
            or ("zh" if _has_cjk(payload.user_query) else dominant_language([answer, *(str(claim.get("text") or "") for claim in claims)]))
        )

        active_settings = self._settings or load()
        llm_warnings: list[str] = []
        if _llm_enabled(payload, active_settings):
            try:
                llm = _try_llm_analysis(
                    client=self._llm_client,
                    settings=active_settings,
                    payload=payload,
                    claims=claims,
                    visible_rows=visible_rows,
                    answer=answer,
                    source=source,
                )
            except Exception as exc:  # noqa: BLE001 - LLM S4 must degrade to deterministic S4
                llm_warnings.append(
                    f"S4 LLM analysis unavailable; using deterministic fallback: {type(exc).__name__}: {exc}"
                )
            else:
                if llm is not None:
                    result = {
                        **dict(structured),
                        "task_id": payload.task_id,
                        "mode": "engineering_analysis",
                        "answer": llm.answer,
                        "engineering_meaning": llm.engineering_meaning,
                        "premises": llm.premises,
                        "failure_modes": llm.failure_modes,
                        "next_action": llm.next_action,
                        "claims": llm.claims,
                        "synthesis_mode": "llm",
                        "token_cost": llm.token_cost,
                        "cost": llm.cost,
                        "s4_analysis": {
                            "source_claim_count": len(claims),
                            "visible_chunk_ids": chunk_ids,
                            "policy": "llm_engineering_analysis",
                        },
                    }
                    return SkillOutput(
                        status="ok",
                        summary=f"S4 engineering LLM ok: {len(llm.claims)} cited claim(s).",
                        structured_result=result,
                        citations=llm.citations,
                        warnings=[
                            *(list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []),
                            *llm.warnings,
                        ],
                        handoff_recommendation="Pass S4 output through V2 before V4 rendering.",
                    )
                llm_warnings.append("S4 LLM returned insufficient; using deterministic fallback.")

        if language == "zh":
            engineering_meaning = f"工程意义仅限于所引证据：{first_claim}"
            premises = f"仅适用于检索到的证据块：{', '.join(chunk_ids)}。"
            failure_modes = "请勿超出所引工况、单位或数值范围进行外推。"
            next_action = "在应用阈值、维护措施或模型假设前，请先核对所引证据块。"
        else:
            engineering_meaning = f"Engineering implication is limited to the cited evidence: {first_claim}"
            premises = f"Apply this only to the retrieved evidence chunks: {', '.join(chunk_ids)}."
            failure_modes = "Do not extrapolate beyond the cited operating condition, units, or numeric values."
            next_action = "Inspect the cited chunks before applying thresholds, maintenance actions, or model assumptions."
        if language == "zh":
            engineering_meaning = f"工程意义仅限于所引证据：{first_claim}"
            premises = f"仅适用于检索到的证据块：{', '.join(chunk_ids)}。"
            failure_modes = "请勿超出所引工况、单位或数值范围进行外推。"
            next_action = "在应用阈值、维护措施或模型假设前，请先核对所引证据块。"
        result = {
            **dict(structured),
            "task_id": payload.task_id,
            "mode": "engineering_analysis",
            "language": language,
            "answer": answer,
            "engineering_meaning": engineering_meaning,
            "premises": premises,
            "failure_modes": failure_modes,
            "next_action": next_action,
            "claims": claims,
            "synthesis_mode": "deterministic",
            "token_cost": None,
            "cost": None,
            "s4_analysis": {
                "source_claim_count": len(claims),
                "visible_chunk_ids": chunk_ids,
                "policy": "deterministic_claim_framing_only",
            },
        }
        return SkillOutput(
            status="ok",
            summary=f"S4 engineering analysis ok: {len(claims)} cited claim(s).",
            structured_result=result,
            citations=_source_citations(source, claims),
            warnings=[
                *(list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []),
                *llm_warnings,
            ],
            handoff_recommendation="Pass S4 output through V2 before V4 rendering.",
        )
