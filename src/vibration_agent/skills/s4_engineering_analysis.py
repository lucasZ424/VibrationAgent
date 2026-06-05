"""S4 deterministic engineering analysis.

S4 is optional and runs after S3 when the user asks in engineering mode. It
adds engineering framing from existing cited claims, then hands the result to V2
so citation visibility remains enforced.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill


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


def _s2_visible_rows(payload: SkillInput) -> Mapping[str, Mapping[str, Any]]:
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


class EngineeringAnalysisSkill(Skill):
    name = "s4_engineering_analysis"

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
        chunk_ids = [str(claim["chunk_id"]) for claim in claims]
        answer = str(structured.get("answer") or source.get("summary") or first_claim).strip()
        engineering_meaning = f"Engineering implication is limited to the cited evidence: {first_claim}"
        premises = f"Apply this only to the retrieved evidence chunks: {', '.join(chunk_ids)}."
        failure_modes = "Do not extrapolate beyond the cited operating condition, units, or numeric values."
        next_action = "Inspect the cited chunks before applying thresholds, maintenance actions, or model assumptions."
        result = {
            **dict(structured),
            "task_id": payload.task_id,
            "mode": "engineering_analysis",
            "answer": answer,
            "engineering_meaning": engineering_meaning,
            "premises": premises,
            "failure_modes": failure_modes,
            "next_action": next_action,
            "claims": claims,
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
            warnings=list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else [],
            handoff_recommendation="Pass S4 output through V2 before V4 rendering.",
        )
