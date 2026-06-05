"""S5 deterministic formula derivation.

S5 is optional and runs after S3 for derivation-mode requests. It builds a
premise -> steps -> conclusion structure only from visible evidence and
axiomatic algebra steps, then hands the result to V2.
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


def _step_text(step: Mapping[str, Any]) -> str:
    source = step.get("source_type")
    marker = "axiomatic" if source == "axiomatic" else f"evidence: {step.get('chunk_id')}"
    return f"{step.get('id')}: {step.get('text')} ({marker})"


class FormulaDerivationSkill(Skill):
    name = "s5_formula_derivation"

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
            warnings=list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else [],
            handoff_recommendation="Pass S5 output through V2 before V4 rendering.",
        )
