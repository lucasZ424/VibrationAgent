"""S5 deterministic formula derivation.

S5 is optional and runs after S3 for derivation-mode requests. It builds a
premise -> steps -> conclusion structure only from visible evidence and
axiomatic algebra steps, then hands the result to V2.
"""
from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from vibration_agent.agent import ModelRegistry, route_task
from vibration_agent.config import Settings, load
from vibration_agent.schemas import Citation, S3LlmClaim, S5DerivationStep, S5LlmResponse, SkillInput, SkillOutput

from .base import Skill
from .formula_rendering import formula_renders_from_assets

_PROMPT_VERSION = "s5_formula_derivation.v1"
_SCHEMA_VERSION = "s5.v1"
S5LlmClient = Any


@dataclass(frozen=True)
class _LlmDerivation:
    answer: str
    premises: str
    minimal_model: str
    conclusion: str
    derivation_steps: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    assets: list[dict[str, Any]]
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
    value = source.get("structured_result")
    return value if isinstance(value, Mapping) else source


def _s2_visible_rows(payload: SkillInput) -> dict[str, Mapping[str, Any]]:
    s2_result = _as_mapping(payload.context.get("s2_result"))
    structured = s2_result.get("structured_result")
    s2_structured = structured if isinstance(structured, Mapping) else s2_result
    rows: dict[str, Mapping[str, Any]] = {}
    retrieval_context = s2_structured.get("retrieval_context")
    if isinstance(retrieval_context, list):
        for row in retrieval_context:
            if isinstance(row, Mapping) and row.get("chunk_id"):
                rows[str(row["chunk_id"])] = row
    return rows


def _claims(structured: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = structured.get("claims")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping) and item.get("text")]


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
        keys=("s5_llm_enabled", "llm_enabled", "use_llm_s5"),
    )
    if value is not None:
        return _as_bool(value, default=False)
    return bool(settings.llm.s5_enabled)


def _formula_assets(row: Mapping[str, Any], claim: Mapping[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for container in (claim, row):
        raw_assets = container.get("assets")
        if not isinstance(raw_assets, list):
            continue
        for asset in raw_assets:
            if isinstance(asset, Mapping) and asset.get("object_type") == "formula":
                assets.append(dict(asset))
    return assets


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
                citations.append(citation)
                seen.add(citation.chunk_id)
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


def _validate_derivation_steps(steps: list[Mapping[str, Any]]) -> list[str]:
    warnings: list[str] = []
    ids: set[str] = set()
    dependencies: dict[str, list[str]] = {}
    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("id") or "")
        if not step_id:
            warnings.append(f"S5 derivation step {index} is missing id.")
            continue
        ids.add(step_id)
        depends_on = step.get("depends_on")
        dependencies[step_id] = [str(dep) for dep in depends_on] if isinstance(depends_on, list) else []
        source_type = step.get("source_type")
        if source_type not in {"evidence", "axiomatic"}:
            warnings.append(f"S5 derivation step {step_id} has invalid source_type.")
        if source_type == "evidence" and not step.get("chunk_id"):
            warnings.append(f"S5 evidence step {step_id} is missing chunk_id.")
        if source_type == "axiomatic" and step.get("chunk_id"):
            warnings.append(f"S5 axiomatic step {step_id} should not cite a chunk.")
    for step_id, deps in dependencies.items():
        if step_id and step_id in deps:
            warnings.append(f"S5 derivation step {step_id} depends on itself.")
        for dep in deps:
            if dep not in ids:
                warnings.append(f"S5 derivation step {step_id} depends on missing step {dep}.")

    visiting: set[str] = set()
    visited: set[str] = set()
    cyclic: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visiting:
            cyclic.add(step_id)
            return
        if step_id in visited:
            return
        visiting.add(step_id)
        for dep in dependencies.get(step_id, []):
            if dep in dependencies:
                visit(dep)
                if dep in cyclic:
                    cyclic.add(step_id)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in dependencies:
        visit(step_id)
    for step_id in sorted(cyclic):
        warnings.append(f"S5 derivation step {step_id} participates in a dependency cycle.")
    return warnings


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
            "You are S5 formula derivation for a vibration engineering assistant.",
            "Use only supplied S3 claims and visible S2 evidence.",
            "Return JSON only. Do not include markdown fences.",
            "Schema: {\"status\":\"ok|insufficient\",\"answer\":\"...\",\"premises\":\"...\",\"minimal_model\":\"...\",\"conclusion\":\"...\",\"derivation_steps\":[{\"id\":\"step_1\",\"source_type\":\"evidence|axiomatic\",\"text\":\"...\",\"chunk_id\":\"...\",\"doc_id\":\"...\",\"pages\":[1],\"asset_ids\":[],\"depends_on\":[]}],\"claims\":[{\"text\":\"...\",\"chunk_id\":\"...\",\"doc_id\":\"...\",\"pages\":[1],\"evidence_type\":\"documented\"}],\"assets\":[],\"warnings\":[]}",
            "Every evidence step must cite a visible chunk_id. Axiomatic steps must explain algebraic assumptions and may omit chunk_id.",
            "The step graph must be acyclic. Do not invent formulas, units, parameters, or measured values.",
            f"query: {payload.user_query}",
            "evidence:",
            "\n\n".join(blocks),
        ]
    )


def _call_llm_client(
    client: S5LlmClient,
    *,
    prompt: str,
    model: str,
    payload: SkillInput,
    claims: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
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
        "query": payload.user_query,
        "mode": "formula_derivation",
        "timeout": provider_settings.timeout,
        "task_id": payload.task_id,
    }
    if hasattr(client, "derive_formula"):
        return client.derive_formula(**kwargs)
    if callable(client):
        return client(**kwargs)
    raise TypeError("S5 LLM client must be callable or expose derive_formula().")


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


def _cost(response: Mapping[str, Any]) -> dict[str, Any] | None:
    value = response.get("cost")
    return dict(value) if isinstance(value, Mapping) else None


def _claim_record(claim: S3LlmClaim) -> dict[str, Any]:
    return claim.model_dump(mode="json")


def _step_record(step: S5DerivationStep) -> dict[str, Any]:
    return step.model_dump(mode="json")


def _try_llm_derivation(
    *,
    client: S5LlmClient | None,
    settings: Settings,
    payload: SkillInput,
    claims: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
    source: Mapping[str, Any],
) -> _LlmDerivation | None:
    if client is None:
        raise RuntimeError("S5 LLM is enabled but no LLM client is configured.")
    model, route = _role_model(settings, payload)
    provider_settings = _provider_settings(settings, model)
    prompt = _evidence_prompt(payload=payload, claims=claims, visible_rows=visible_rows)
    raw_response = _response_mapping(
        _call_llm_client(
            client,
            prompt=prompt,
            model=model,
            payload=payload,
            claims=claims,
            visible_rows=visible_rows,
            provider_settings=provider_settings,
        )
    )
    if raw_response.get("refusal"):
        raise RuntimeError("S5 LLM refused the request.")
    response = S5LlmResponse.model_validate(raw_response)
    if response.status == "insufficient":
        return None
    if response.status in {"refusal", "refused"}:
        raise RuntimeError("S5 LLM refused the request.")
    required_sections = {
        "answer": response.answer,
        "premises": response.premises,
        "minimal_model": response.minimal_model,
        "conclusion": response.conclusion,
    }
    missing_sections = [key for key, value in required_sections.items() if not value.strip()]
    if missing_sections:
        raise RuntimeError("S5 LLM response missing required derivation fields: " + ", ".join(missing_sections))
    if not response.claims:
        raise RuntimeError("S5 LLM response did not contain cited claims.")
    if not response.derivation_steps:
        raise RuntimeError("S5 LLM response did not contain derivation steps.")
    steps = [_step_record(step) for step in response.derivation_steps]
    step_warnings = _validate_derivation_steps(steps)
    if step_warnings:
        raise RuntimeError("; ".join(step_warnings))
    claim_records = [_claim_record(claim) for claim in response.claims]
    return _LlmDerivation(
        answer=response.answer.strip(),
        premises=response.premises.strip(),
        minimal_model=response.minimal_model.strip(),
        conclusion=response.conclusion.strip(),
        derivation_steps=steps,
        claims=claim_records,
        assets=[dict(asset) for asset in response.assets if isinstance(asset, Mapping)],
        citations=_visible_citations(source, claim_records, visible_rows),
        token_cost=_token_cost(raw_response),
        cost=_cost(raw_response),
        warnings=[*response.warnings, f"S5 LLM route: {route['role']} -> {model}."],
    )


def _step_text(step: Mapping[str, Any]) -> str:
    source = step.get("source_type")
    marker = "axiomatic" if source == "axiomatic" else f"evidence: {step.get('chunk_id')}"
    return f"{step.get('id')}: {step.get('text')} ({marker})"


class FormulaDerivationSkill(Skill):
    name = "s5_formula_derivation"

    def __init__(self, *, settings: Settings | None = None, llm_client: S5LlmClient | None = None) -> None:
        self._settings = settings
        self._llm_client = llm_client

    def run(self, payload: SkillInput) -> SkillOutput:
        if payload.user_mode != "derivation":
            return SkillOutput(
                status="insufficient",
                summary="S5 skipped: formula derivation requires user_mode='derivation'.",
                structured_result={"task_id": payload.task_id, "skip_reason": "user_mode"},
                handoff_recommendation="Use user_mode='derivation' to request S5 formula derivation.",
            )

        source = _source_output(payload)
        structured = _structured(source)
        visible_rows = _s2_visible_rows(payload)
        claims = [claim for claim in _claims(structured) if str(claim.get("chunk_id") or "") in visible_rows]
        if not claims:
            return SkillOutput(
                status="insufficient",
                summary="S5 skipped: formula derivation requires cited claims visible to S2.",
                structured_result={"task_id": payload.task_id, "skip_reason": "insufficient_evidence"},
                warnings=["S5 found no cited claims tied to visible retrieval evidence."],
                handoff_recommendation="Run S2/S3 with enough cited evidence before S5.",
            )

        active_settings = self._settings or load()
        llm_warnings: list[str] = []
        if _llm_enabled(payload, active_settings):
            try:
                llm = _try_llm_derivation(
                    client=self._llm_client,
                    settings=active_settings,
                    payload=payload,
                    claims=claims,
                    visible_rows=visible_rows,
                    source=source,
                )
            except Exception as exc:  # noqa: BLE001 - LLM S5 must degrade to deterministic S5
                llm_warnings.append(
                    f"S5 LLM derivation unavailable; using deterministic fallback: {type(exc).__name__}: {exc}"
                )
            else:
                if llm is not None:
                    formula_renders, formula_warnings = formula_renders_from_assets(llm.assets)
                    result = {
                        **dict(structured),
                        "task_id": payload.task_id,
                        "mode": "formula_derivation",
                        "answer": llm.answer,
                        "premises": llm.premises,
                        "minimal_model": llm.minimal_model,
                        "conclusion": llm.conclusion,
                        "derivation_steps": llm.derivation_steps,
                        "claims": llm.claims,
                        "assets": llm.assets,
                        "formula_renders": formula_renders,
                        "synthesis_mode": "llm",
                        "token_cost": llm.token_cost,
                        "cost": llm.cost,
                        "s5_derivation": {
                            "source_claim_count": len(claims),
                            "visible_chunk_ids": [str(claim["chunk_id"]) for claim in claims],
                            "policy": "llm_evidence_and_axiomatic_steps",
                        },
                    }
                    return SkillOutput(
                        status="ok",
                        summary=f"S5 formula LLM ok: {len(llm.derivation_steps)} step(s).",
                        structured_result=result,
                        citations=llm.citations,
                        warnings=[
                            *(list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []),
                            *llm.warnings,
                            *formula_warnings,
                        ],
                        handoff_recommendation="Pass S5 output through V2 before V4 rendering.",
                    )
                llm_warnings.append("S5 LLM returned insufficient; using deterministic fallback.")

        evidence_claim = claims[0]
        chunk_id = str(evidence_claim.get("chunk_id"))
        row = visible_rows[chunk_id]
        formula_assets = _formula_assets(row, evidence_claim)
        asset_ids = [str(asset["asset_id"]) for asset in formula_assets if asset.get("asset_id")]
        formula_text = str(evidence_claim.get("formula") or evidence_claim.get("text") or "").strip()
        if formula_assets:
            formula_text = str(formula_assets[0].get("text_preview") or formula_assets[0].get("text") or formula_text).strip()

        steps = [
            {
                "id": "step_1",
                "source_type": "evidence",
                "text": f"Use the cited relation: {formula_text}",
                "chunk_id": chunk_id,
                "doc_id": evidence_claim.get("doc_id") or row.get("doc_id"),
                "pages": evidence_claim.get("pages") if isinstance(evidence_claim.get("pages"), list) else row.get("pages"),
                "asset_ids": asset_ids,
                "depends_on": [],
            },
            {
                "id": "step_2",
                "source_type": "axiomatic",
                "text": "Rearrange equal terms algebraically without introducing new measured quantities.",
                "depends_on": ["step_1"],
            },
        ]
        warnings = _validate_derivation_steps(steps)
        if warnings:
            return SkillOutput(
                status="insufficient",
                summary="S5 skipped: derivation steps are structurally invalid.",
                structured_result={"task_id": payload.task_id, "skip_reason": "invalid_steps", "derivation_steps": steps},
                warnings=warnings,
                handoff_recommendation="Fix missing steps or cyclic dependencies before S5.",
            )

        premises = f"Premise: {formula_text} (evidence: {chunk_id})."
        step_block = "\n".join(_step_text(step) for step in steps)
        conclusion = "Conclusion: the derivation is limited to the cited relation and axiomatic algebraic rearrangement."
        minimal_model = "\n".join(part for part in (formula_text, step_block) if part)
        formula_renders, formula_warnings = formula_renders_from_assets(formula_assets)
        result = {
            **dict(structured),
            "task_id": payload.task_id,
            "mode": "formula_derivation",
            "answer": f"{premises}\n{step_block}\n{conclusion}",
            "premises": premises,
            "minimal_model": minimal_model,
            "conclusion": conclusion,
            "derivation_steps": steps,
            "claims": claims,
            "assets": formula_assets,
            "formula_renders": formula_renders,
            "synthesis_mode": "deterministic",
            "token_cost": None,
            "cost": None,
            "s5_derivation": {
                "source_claim_count": len(claims),
                "visible_chunk_ids": [chunk_id],
                "policy": "evidence_and_axiomatic_steps_only",
            },
        }
        return SkillOutput(
            status="ok",
            summary=f"S5 formula derivation ok: {len(steps)} step(s).",
            structured_result=result,
            citations=_source_citations(source, claims),
            warnings=[
                *(list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []),
                *llm_warnings,
                *formula_warnings,
            ],
            handoff_recommendation="Pass S5 output through V2 before V4 rendering.",
        )
