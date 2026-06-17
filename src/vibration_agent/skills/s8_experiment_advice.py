"""S8 experiment advice prototype.

S8 is a default-off advisory skill. It turns visible vibration evidence into
measurement and validation advice, but it does not invent thresholds or replace
site safety procedures.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

_SCHEMA_VERSION = "s8.experiment_advice.v1"
_NUMERIC_TERM_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:hz|khz|rpm|cpm|mm/s|mm/s2|m/s2|g|db|um|micron|mil|x|%)(?=\W|$)",
    re.IGNORECASE,
)

_ADVICE_RULES = (
    {
        "experiment_focus": "runup_or_resonance_validation",
        "keywords": {
            "critical",
            "speed",
            "resonance",
            "runup",
            "run-up",
            "damping",
            "zeta",
            "\u4e34\u754c",
            "\u4e34\u754c\u8f6c\u901f",
            "\u5171\u632f",
            "\u963b\u5c3c",
            "\u5347\u901f",
        },
        "assumptions": [
            "The cited evidence concerns resonance, critical speed, runup, or damping behavior.",
            "Operating state changes can be observed under a controlled test plan.",
        ],
        "required_measurements": [
            "Speed or phase reference aligned with each vibration record.",
            "Radial vibration response at relevant bearing or casing locations.",
            "Operating condition notes for load, speed transition, and machine state.",
        ],
        "sensor_layout": [
            "Place vibration sensors on documented bearing or casing locations before comparing response trends.",
            "Use a speed or phase reference when interpreting resonance passage or synchronous behavior.",
        ],
        "validation_steps": [
            "Compare response trends before and after the operating-state change using the same measurement chain.",
            "Treat any quantitative damping or critical-speed value as unknown until it is measured or cited.",
        ],
        "safety_limits": [
            "Do not extend a runup beyond approved site procedures based on S8 advice alone.",
            "Stop the test and follow site procedures if measured behavior indicates unsafe operation.",
        ],
    },
    {
        "experiment_focus": "bearing_fault_measurement_plan",
        "keywords": {
            "bearing",
            "fault",
            "envelope",
            "outer",
            "inner",
            "race",
            "\u8f74\u627f",
            "\u6545\u969c",
            "\u5305\u7edc",
            "\u5916\u5708",
            "\u5185\u5708",
        },
        "assumptions": [
            "The cited evidence concerns bearing condition, bearing faults, or envelope analysis.",
            "Bearing geometry and operating condition can be obtained before quantitative interpretation.",
        ],
        "required_measurements": [
            "Raw vibration waveform from the bearing location under a known operating condition.",
            "Speed reference or operating-speed record for every captured waveform.",
            "Bearing geometry or documented fault-frequency references before naming fault frequencies.",
        ],
        "sensor_layout": [
            "Place the primary vibration sensor on the bearing housing or documented measurement point.",
            "Keep mounting method and channel orientation consistent across comparison runs.",
        ],
        "validation_steps": [
            "Preserve raw waveform data before applying envelope or spectral processing.",
            "Confirm that any named bearing fault frequency is backed by geometry or cited evidence.",
        ],
        "safety_limits": [
            "Do not infer bearing replacement urgency from S8 advice without plant criteria or cited limits.",
            "Escalate to a qualified reliability or safety procedure if evidence suggests active deterioration.",
        ],
    },
    {
        "experiment_focus": "synchronous_unbalance_validation",
        "keywords": {
            "unbalance",
            "synchronous",
            "1x",
            "one-times",
            "phase",
            "\u4e0d\u5e73\u8861",
            "\u540c\u6b65",
            "\u76f8\u4f4d",
            "1\u500d\u9891",
        },
        "assumptions": [
            "The cited evidence concerns synchronous rotor response or possible unbalance.",
            "A repeatable speed or phase reference is available for comparison.",
        ],
        "required_measurements": [
            "Vibration amplitude and phase under the same operating condition.",
            "Speed or phase reference synchronized with the vibration channels.",
            "Machine configuration notes before and after any correction or maintenance action.",
        ],
        "sensor_layout": [
            "Use consistent radial measurement points across baseline and follow-up captures.",
            "Keep phase reference placement stable when comparing synchronous response.",
        ],
        "validation_steps": [
            "Compare synchronous response changes against the cited evidence and measured operating condition.",
            "Do not calculate correction masses or acceptance limits without a separate cited procedure.",
        ],
        "safety_limits": [
            "Do not perform correction trials without an approved balance and lockout procedure.",
            "Do not treat S8 advisory output as an acceptance test or machine-clearance decision.",
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
        keys=("s8_enabled", "experiment_advice_enabled", "use_s8"),
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
        haystack = " ".join([text, str(row.get("topic") or ""), str(row.get("title") or "")]).casefold()
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


def _confirmed_facts(refs: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for ref in refs:
        facts.append(
            {
                "text": str(ref.get("quote") or ""),
                "evidence_refs": [
                    {
                        "chunk_id": ref.get("chunk_id"),
                        "doc_id": ref.get("doc_id"),
                        "pages": ref.get("pages") if isinstance(ref.get("pages"), list) else [],
                    }
                ],
            }
        )
    return facts


def _omitted_numeric_terms(payload: SkillInput, rows: list[dict[str, Any]]) -> list[str]:
    evidence_text = "\n".join(_row_text(row) for row in rows).casefold()
    omitted: list[str] = []
    for match in _NUMERIC_TERM_RE.finditer(payload.user_query):
        term = re.sub(r"\s+", " ", match.group(0).strip()).casefold()
        if term and term not in evidence_text and term not in omitted:
            omitted.append(term)
    return omitted


def _experiment_plans(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for index, rule in enumerate(_ADVICE_RULES, start=1):
        refs = _evidence_refs(rows, set(rule["keywords"]))
        if not refs:
            continue
        plans.append(
            {
                "advice_id": f"s8_plan_{index}",
                "experiment_focus": rule["experiment_focus"],
                "confirmed_facts": _confirmed_facts(refs),
                "assumptions": list(rule["assumptions"]),
                "required_measurements": list(rule["required_measurements"]),
                "sensor_layout": list(rule["sensor_layout"]),
                "validation_steps": list(rule["validation_steps"]),
                "safety_limits": list(rule["safety_limits"]),
                "evidence_refs": refs,
            }
        )
    return plans


def _citations(plans: list[Mapping[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for plan in plans:
        refs = plan.get("evidence_refs")
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


def _base_result(payload: SkillInput, *, mode: str, plans: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "task_id": payload.task_id,
        "query": payload.user_query,
        "mode": mode,
        "experiment_plans": plans or [],
        "routing": {"default_chain": False, "requires_activation_gate": True},
    }


class ExperimentAdviceSkill(Skill):
    name = "s8_experiment_advice"

    def run(self, payload: SkillInput) -> SkillOutput:
        if not _skill_enabled(payload):
            result = _base_result(payload, mode="disabled")
            result["limitations"] = ["Set s8_enabled=true for explicit experiment-advice output."]
            return SkillOutput(
                status="insufficient",
                summary="S8 skipped: experiment advice is default-off.",
                structured_result=result,
                handoff_recommendation="Enable S8 explicitly or wait for the routing activation gate.",
            )

        rows = _visible_rows(payload)
        if not rows:
            result = _base_result(payload, mode="advisory")
            result["limitations"] = ["Experiment advice requires visible S2 evidence or explicit retrieval rows."]
            return SkillOutput(
                status="insufficient",
                summary="S8 experiment advice insufficient: no visible evidence.",
                structured_result=result,
                warnings=["S8 found no visible evidence to support measurement advice."],
                handoff_recommendation="Run S2 retrieval first, then invoke S8 explicitly.",
            )

        plans = _experiment_plans(rows)
        omitted = _omitted_numeric_terms(payload, rows)
        if not plans:
            result = _base_result(payload, mode="advisory")
            result["limitations"] = [
                "No calibrated experiment-advice rule matched the visible evidence.",
                "Do not infer measurement thresholds from world knowledge alone.",
            ]
            result["omitted_unsupported_thresholds"] = omitted
            return SkillOutput(
                status="insufficient",
                summary="S8 experiment advice insufficient: no calibrated advice rule matched the evidence.",
                structured_result=result,
                handoff_recommendation="Broaden retrieval evidence or add a labeled S8 rule.",
            )

        result = _base_result(payload, mode="advisory", plans=plans)
        result["omitted_unsupported_thresholds"] = omitted
        result["limitations"] = [
            "S8 is advisory and does not replace approved test procedures or site safety rules.",
            "Numeric thresholds must be cited, measured, or explicitly provided as accepted project constraints.",
        ]
        warnings = []
        if omitted:
            warnings.append("S8 omitted numeric query terms that were not visible in evidence.")
        return SkillOutput(
            status="ok",
            summary=f"S8 experiment advice ok: {len(plans)} plan(s).",
            structured_result=result,
            citations=_citations(plans),
            warnings=warnings,
            handoff_recommendation="Use S8 as measurement-planning context only; final answers still require V2/V4-bound synthesis.",
        )


__all__ = ["ExperimentAdviceSkill"]
