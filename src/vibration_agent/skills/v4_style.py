"""V4 output-style shaping skill.

V4 is a formatting layer. It renders upstream S3 output into the fixed
engineering answer template without adding new domain claims.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError

from ..schemas import Citation, SkillInput, SkillOutput
from .base import Skill
from .formula_rendering import normalize_formula_renders

_SECTION_DEFS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("conclusion", ("conclusion", "answer")),
    ("engineering_meaning", ("engineering_meaning", "engineering_context", "why_it_matters")),
    ("premises", ("premises", "assumptions", "applicability", "conditions")),
    ("failure_modes", ("failure_modes", "caveats", "common_pitfalls", "limitations")),
    ("minimal_model", ("minimal_model", "formula", "formulas", "equations")),
    ("next_action", ("next_action", "next_steps", "recommendation", "recommendations")),
)
_TITLES: dict[str, dict[str, str]] = {
    "zh": {
        "conclusion": "结论",
        "engineering_meaning": "工程意义",
        "premises": "适用前提",
        "failure_modes": "失效条件/常见误区",
        "minimal_model": "最简模型/公式",
        "next_action": "下一步建议",
        "evidence": "证据",
    },
    "en": {
        "conclusion": "Conclusion",
        "engineering_meaning": "Engineering Meaning",
        "premises": "Premises",
        "failure_modes": "Failure Conditions / Common Pitfalls",
        "minimal_model": "Minimal Model / Formula",
        "next_action": "Next Actions",
        "evidence": "Evidence",
    },
}
_EVIDENCE_TYPE_LABELS: dict[str, dict[str, str]] = {
    "zh": {"documented": "已记录", "inferred": "推断", "heuristic": "启发式"},
    "en": {"documented": "documented", "inferred": "inferred", "heuristic": "heuristic"},
}
_STATUS_PREFIXES_TO_IGNORE = tuple(f"{prefix} " for prefix in (*[f"S{index}" for index in range(1, 9)], "V1", "V2", "V3", "V4"))

_TITLES["zh"] = {
    "conclusion": "结论",
    "engineering_meaning": "工程意义",
    "premises": "适用前提",
    "failure_modes": "失效条件/常见误区",
    "minimal_model": "最简模型/公式",
    "next_action": "下一步建议",
    "evidence": "证据",
}
_EVIDENCE_TYPE_LABELS["zh"] = {"documented": "已记录", "inferred": "推断", "heuristic": "启发式"}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, SkillOutput):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    return {}


def _source_payload(payload: SkillInput) -> Mapping[str, Any]:
    for key in ("upstream_result", "s3_result", "skill_output"):
        source = _as_mapping(payload.context.get(key))
        if source:
            return source
    return payload.context


def _structured_result(source: Mapping[str, Any]) -> Mapping[str, Any]:
    structured = source.get("structured_result")
    if isinstance(structured, Mapping):
        return structured
    return source


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        parts = [_clean_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    return str(value).strip()


def _section_values_text(structured: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key, aliases in _SECTION_DEFS:
        value = _first_section_value(structured, key, aliases)
        if value:
            parts.append(value)
    for claim in _claim_records(structured):
        parts.append(_clean_text(claim.get("text")))
    return "\n".join(part for part in parts if part)


def _language(source: Mapping[str, Any], structured: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    for container in (context, structured, source):
        value = container.get("answer_language") or container.get("query_language")
        if value in {"zh", "en"}:
            return str(value)
        value = container.get("language")
        if value in {"zh", "en"}:
            return str(value)
    text = "\n".join(
        part
        for part in (
            _clean_text(structured.get("answer")),
            _clean_text(source.get("answer")),
            _section_values_text(structured),
        )
        if part
    )
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    return "zh" if cjk >= latin else "en"


def _title(section_key: str, language: str) -> str:
    return _TITLES.get(language, _TITLES["zh"])[section_key]


def _first_section_value(structured: Mapping[str, Any], key: str, aliases: tuple[str, ...]) -> str:
    sections = structured.get("sections")
    section_map = sections if isinstance(sections, Mapping) else {}
    for candidate in (key, *aliases):
        value = _clean_text(structured.get(candidate))
        if value:
            return value
        value = _clean_text(section_map.get(candidate))
        if value:
            return value
    return ""


def _claim_records(structured: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    claims = structured.get("claims")
    if not isinstance(claims, list):
        return []
    return [claim for claim in claims if isinstance(claim, Mapping)]


def _citation_records(source: Mapping[str, Any], structured: Mapping[str, Any]) -> tuple[list[Citation], list[str]]:
    citations: list[Citation] = []
    warnings: list[str] = []
    seen: set[str] = set()
    for container in (source, structured):
        raw = container.get("citations")
        if not isinstance(raw, list):
            continue
        for item in raw:
            try:
                if isinstance(item, Citation):
                    citation = item
                elif isinstance(item, Mapping):
                    citation = Citation.model_validate(item)
                else:
                    continue
            except (TypeError, ValueError, ValidationError) as exc:
                warnings.append(f"V4 dropped malformed citation: {exc}")
                continue
            if citation.chunk_id not in seen:
                seen.add(citation.chunk_id)
                citations.append(citation)
    if citations:
        return citations, warnings

    for claim in _claim_records(structured):
        chunk_id = claim.get("chunk_id")
        doc_id = claim.get("doc_id")
        if not chunk_id or not doc_id:
            continue
        try:
            citation = Citation(
                chunk_id=str(chunk_id),
                doc_id=str(doc_id),
                pages=claim.get("pages") if isinstance(claim.get("pages"), list) else None,
                evidence_type=claim.get("evidence_type") or "documented",
                confidence=float(claim.get("confidence", 1.0) or 1.0),
                source_filename=str(claim["source_filename"]) if claim.get("source_filename") else None,
                source_title=str(claim["source_title"]) if claim.get("source_title") else None,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            warnings.append(f"V4 dropped malformed claim citation: {exc}")
            continue
        if citation.chunk_id not in seen:
            seen.add(citation.chunk_id)
            citations.append(citation)
    return citations, warnings


def _compact_page_runs(pages: list[int]) -> list[str]:
    unique_pages = sorted(set(pages))
    if not unique_pages:
        return []
    runs: list[str] = []
    start = previous = unique_pages[0]
    for page in unique_pages[1:]:
        if page == previous + 1:
            previous = page
            continue
        runs.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = page
    runs.append(str(start) if start == previous else f"{start}-{previous}")
    return runs


def _pages_label(pages: list[int] | None, language: str) -> str:
    if language == "zh":
        if not pages:
            return "页码未知"
        return f"第{','.join(_compact_page_runs(pages))}页"
    if not pages:
        return "页码未知" if language == "zh" else "pages unknown"
    compacted = ",".join(_compact_page_runs(pages))
    if language == "zh":
        return f"第{compacted}页"
    return f"p.{compacted}" if len(set(pages)) == 1 else f"pp.{compacted}"


def _asset_ids_from_claim(claim: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    raw_ids = claim.get("asset_ids")
    if isinstance(raw_ids, list):
        ids.extend(str(asset_id) for asset_id in raw_ids if asset_id)
    raw_assets = claim.get("assets")
    if isinstance(raw_assets, list):
        for asset in raw_assets:
            if isinstance(asset, Mapping) and asset.get("asset_id"):
                ids.append(str(asset["asset_id"]))
    return list(dict.fromkeys(ids))


def _asset_records(structured: Mapping[str, Any], claims: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    anonymous: list[dict[str, Any]] = []
    raw_assets = structured.get("assets")
    if isinstance(raw_assets, list):
        for asset in raw_assets:
            if not isinstance(asset, Mapping):
                continue
            asset_dict = dict(asset)
            asset_id = asset_dict.get("asset_id")
            if asset_id:
                records[str(asset_id)] = asset_dict
            else:
                anonymous.append(asset_dict)
    for claim in claims:
        for asset_id in _asset_ids_from_claim(claim):
            records.setdefault(asset_id, {"asset_id": asset_id})
    return [*records.values(), *anonymous]


def _evidence_type_label(evidence_type: str, language: str) -> str:
    return _EVIDENCE_TYPE_LABELS.get(language, _EVIDENCE_TYPE_LABELS["zh"]).get(evidence_type, evidence_type)


def _evidence_lines(citations: list[Citation], claims: list[Mapping[str, Any]], language: str) -> list[str]:
    claim_by_chunk: dict[str, str] = {}
    assets_by_chunk: dict[str, list[str]] = {}
    for claim in claims:
        chunk_id = claim.get("chunk_id")
        if not chunk_id:
            continue
        chunk_key = str(chunk_id)
        text = _clean_text(claim.get("text"))
        if text and chunk_key not in claim_by_chunk:
            claim_by_chunk[chunk_key] = text
        asset_ids = _asset_ids_from_claim(claim)
        if asset_ids:
            assets_by_chunk[chunk_key] = asset_ids

    lines: list[str] = []
    for citation in citations:
        evidence_type = _evidence_type_label(citation.evidence_type, language)
        source_label = citation.source_filename or citation.source_title or citation.doc_id
        base = f"- {source_label} ({_pages_label(citation.pages, language)}, {evidence_type})"
        claim_text = claim_by_chunk.get(citation.chunk_id)
        asset_ids = assets_by_chunk.get(citation.chunk_id, [])
        if claim_text:
            line = f"{base}: {claim_text}"
        else:
            line = base
        if asset_ids:
            label = "资产" if language == "zh" else "assets"
            line = f"{line} [{label}: {', '.join(asset_ids)}]"
        lines.append(line)
    return lines


def _render_sections(sections: list[tuple[str, str]]) -> str:
    rendered: list[str] = []
    for title, body in sections:
        rendered.append(f"## {title}\n{body}")
    return "\n\n".join(rendered)


class OutputStyleSkill(Skill):
    """Render upstream evidence-bound answers into the engineering template."""

    name = "v4_style"

    def run(self, payload: SkillInput) -> SkillOutput:
        source = _source_payload(payload)
        structured = _structured_result(source)
        upstream_status = source.get("status")
        warnings = list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []
        language = _language(source, structured, payload.context)

        content_sections: list[tuple[str, str]] = []
        section_keys: list[str] = []
        for key, aliases in _SECTION_DEFS:
            body = _first_section_value(structured, key, aliases)
            if key == "conclusion" and not body:
                body = _clean_text(source.get("answer"))
            if key == "conclusion" and not body:
                summary = _clean_text(source.get("summary"))
                if summary and not summary.startswith(_STATUS_PREFIXES_TO_IGNORE):
                    body = summary
            if body:
                content_sections.append((_title(key, language), body))
                section_keys.append(key)

        citations, citation_warnings = _citation_records(source, structured)
        claims = _claim_records(structured)
        assets = _asset_records(structured, claims)
        formula_renders, formula_warnings = normalize_formula_renders(structured.get("formula_renders"), assets)
        evidence = _evidence_lines(citations, claims, language)
        if evidence:
            content_sections.append((_title("evidence", language), "\n".join(evidence)))
            section_keys.append("evidence")

        warnings = [*warnings, *citation_warnings, *formula_warnings]
        if not content_sections:
            status = upstream_status if upstream_status in {"insufficient", "fail"} else "insufficient"
            return SkillOutput(
                status=status,
                summary="V4 requires upstream answer sections or citations to render.",
                structured_result={
                    "task_id": payload.task_id,
                    "language": language,
                    "section_keys": [],
                    "assets": assets,
                    "formula_renders": formula_renders,
                },
                citations=citations,
                warnings=[*warnings, "No renderable upstream content supplied to V4."],
                handoff_recommendation="Run S3 first and pass its SkillOutput as context.s3_result.",
            )

        answer = _render_sections(content_sections)
        status = upstream_status if upstream_status in {"ok", "insufficient", "fail"} else "ok"
        return SkillOutput(
            status=status,
            summary=f"V4 style ok: {len(content_sections)} section(s), {len(citations)} citation(s).",
            structured_result={
                "task_id": payload.task_id,
                "language": language,
                "answer": answer,
                "section_keys": section_keys,
                "sections": {key: body for key, (_, body) in zip(section_keys, content_sections, strict=True)},
                "assets": assets,
                "formula_renders": formula_renders,
                "source_status": upstream_status,
            },
            citations=citations,
            warnings=warnings,
            handoff_recommendation="Return structured_result.answer to the user.",
        )
