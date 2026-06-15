"""S7 model selection prototype.

S7 is a default-off advisory skill. It recommends analysis model families from
visible evidence and explicit assumptions, but it does not execute modeling.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

_SCHEMA_VERSION = "s7.model_selection.v1"
_MODEL_RULES = (
    {
        "model_family": "rotor_unbalance_synchronous_response",
        "keywords": {"unbalance", "synchronous", "1x", "one-times", "一次", "不平衡", "同步"},
        "purpose": "Evaluate synchronous rotor response associated with unbalance evidence.",
        "assumptions": [
            "The response is dominated by synchronous excitation.",
            "Rotor speed and phase references are available before applying the model.",
        ],
        "limitations": [
            "Do not use this recommendation to diagnose bearing defects without separate evidence.",
            "This advisory does not estimate balance correction masses.",
        ],
    },
    {
        "model_family": "critical_speed_runup_response",
        "keywords": {"critical", "speed", "resonance", "runup", "run-up", "damping", "zeta", "临界", "共振", "阻尼"},
        "purpose": "Use a critical-speed/runup response model to reason about resonance passage and damping effects.",
        "assumptions": [
            "The cited evidence discusses critical speed, resonance, damping, or runup behavior.",
            "Operating speed range is known before quantitative use.",
        ],
        "limitations": [
            "This advisory does not invent critical-speed values or damping ratios.",
            "Quantitative thresholds require cited measurements or standards.",
        ],
    },
    {
        "model_family": "bearing_fault_envelope_analysis",
        "keywords": {"bearing", "fault", "envelope", "outer", "inner", "race", "轴承", "故障", "包络"},
        "purpose": "Consider envelope/spectral analysis only when bearing-fault evidence is visible.",
        "assumptions": [
            "The evidence includes bearing fault or envelope-analysis context.",
            "Sampling rate and bearing geometry are available before frequency calculation.",
        ],
        "limitations": [
            "This advisory does not compute BPFO/BPFI/BSF/FTF values.",
            "Fault-frequency claims need cited bearing geometry or measured spectra.",
        ],
    },
)


def _as_bool(value: Any, *, default: bool = False) -> bool:
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


def _skill_enabled(payload: SkillInput) -> bool:
    value = _first_present(
        payload.constraints,
        payload.context,
        keys=("s7_enabled", "model_selection_enabled", "use_s7"),
    )
    return _as_bool(value, default=False)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, SkillOutput):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    return {}


def _s2_structured(payload: SkillInput) -> Mapping[str, Any]:
    s2_result = _as_mapping(payload.context.get("s2_result"))
    structured = s2_result.get("structured_result")
    return structured if isinstance(structured, Mapping) else s2_result


def _visible_rows(payload: SkillInput) -> list[dict[str, Any]]:
    rows = _s2_structured(payload).get("retrieval_context")
    if not isinstance(rows, list):
        rows = payload.retrieval_results
    return [dict(row) for row in rows if isinstance(row, Mapping) and row.get("chunk_id")]


def _row_text(row: Mapping[str, Any]) -> str:
    return str(row.get("text") or row.get("api_context") or "")


def _evidence_refs(rows: list[dict[str, Any]], keywords: set[str], *, max_refs: int = 2) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for row in rows:
        text = _row_text(row)
        haystack = " ".join(
            [
                text,
                str(row.get("topic") or ""),
                str(row.get("title") or ""),
            ]
        ).casefold()
        if not any(keyword.casefold() in haystack for keyword in keywords):
            continue
        refs.append(
            {
                "chunk_id": str(row["chunk_id"]),
                "doc_id": str(row.get("doc_id") or ""),
                "pages": list(row.get("pages") or []),
                "evidence_type": "documented",
                "quote": text[:240],
            }
        )
        if len(refs) >= max_refs:
            break
    return refs


def _recommendations(payload: SkillInput, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    for index, rule in enumerate(_MODEL_RULES, start=1):
        keywords = set(rule["keywords"])
        refs = _evidence_refs(rows, keywords)
        if not refs:
            continue
        recommendations.append(
            {
                "recommendation_id": f"s7_rec_{index}",
                "model_family": rule["model_family"],
                "purpose": rule["purpose"],
                "evidence_refs": refs,
                "assumptions": list(rule["assumptions"]),
                "limitations": list(rule["limitations"]),
                "confidence": 0.7 if len(refs) == 1 else 0.8,
                "next_steps": [
                    "Confirm measurement channels, units, and operating condition coverage.",
                    "Run the selected model only after numeric inputs are cited or provided explicitly.",
                ],
            }
        )
    return recommendations


def _citations(recommendations: list[Mapping[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for recommendation in recommendations:
        refs = recommendation.get("evidence_refs")
        if not isinstance(refs, list):
            continue
        for ref in refs:
            if not isinstance(ref, Mapping):
                continue
            chunk_id = str(ref.get("chunk_id") or "")
            doc_id = str(ref.get("doc_id") or "")
            if not chunk_id or not doc_id or chunk_id in seen:
                continue
            citations.append(
                Citation(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    pages=ref.get("pages") if isinstance(ref.get("pages"), list) else None,
                )
            )
            seen.add(chunk_id)
    return citations


class ModelSelectionSkill(Skill):
    name = "s7_model_selection"

    def run(self, payload: SkillInput) -> SkillOutput:
        if not _skill_enabled(payload):
            return SkillOutput(
                status="insufficient",
                summary="S7 skipped: model selection is default-off.",
                structured_result={
                    "schema_version": _SCHEMA_VERSION,
                    "task_id": payload.task_id,
                    "query": payload.user_query,
                    "mode": "disabled",
                    "recommendations": [],
                    "limitations": ["Set s7_enabled=true for explicit model-selection advisory output."],
                    "routing": {"default_chain": False, "requires_activation_gate": True},
                },
                handoff_recommendation="Enable S7 explicitly or wait for the routing activation gate.",
            )

        rows = _visible_rows(payload)
        if not rows:
            return SkillOutput(
                status="insufficient",
                summary="S7 model selection insufficient: no visible evidence.",
                structured_result={
                    "schema_version": _SCHEMA_VERSION,
                    "task_id": payload.task_id,
                    "query": payload.user_query,
                    "mode": "advisory",
                    "recommendations": [],
                    "limitations": ["Model selection requires visible S2 evidence or explicit retrieval rows."],
                    "routing": {"default_chain": False, "requires_activation_gate": True},
                },
                warnings=["S7 found no visible evidence to support model recommendations."],
                handoff_recommendation="Run S2 retrieval first, then invoke S7 explicitly.",
            )

        recommendations = _recommendations(payload, rows)
        if not recommendations:
            return SkillOutput(
                status="insufficient",
                summary="S7 model selection insufficient: no calibrated model family matched the evidence.",
                structured_result={
                    "schema_version": _SCHEMA_VERSION,
                    "task_id": payload.task_id,
                    "query": payload.user_query,
                    "mode": "advisory",
                    "recommendations": [],
                    "limitations": [
                        "No calibrated model-selection rule matched the visible evidence.",
                        "Do not infer a model family from world knowledge alone.",
                    ],
                    "routing": {"default_chain": False, "requires_activation_gate": True},
                },
                handoff_recommendation="Broaden retrieval evidence or add a labeled S7 rule.",
            )

        return SkillOutput(
            status="ok",
            summary=f"S7 model selection ok: {len(recommendations)} recommendation(s).",
            structured_result={
                "schema_version": _SCHEMA_VERSION,
                "task_id": payload.task_id,
                "query": payload.user_query,
                "mode": "advisory",
                "recommendations": recommendations,
                "limitations": [
                    "S7 is advisory and does not execute modeling.",
                    "All quantitative model inputs must be separately cited or explicitly provided.",
                ],
                "routing": {"default_chain": False, "requires_activation_gate": True},
            },
            citations=_citations(recommendations),
            handoff_recommendation="Use S7 recommendations as advisory context only; final answers still require V2/V4-bound synthesis.",
        )


__all__ = ["ModelSelectionSkill"]
