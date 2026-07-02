"""V2 citation check quality layer.

V2 runs after S3 and before V4. It verifies that S3 claims cite chunks visible
in the S2 retrieval set and removes unsupported claims before rendering.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from vibration_agent.knowledge.evidence import citation_from_evidence
from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.schemas import Citation, SkillInput, SkillOutput

from .base import Skill

_REF_RE = re.compile(r"\[([A-Za-z0-9_.:/#-]+)\]")
_INLINE_EVIDENCE_REF_RE = re.compile(
    r"(?:\(evidence\s*:\s*|（证据\s*[:：]\s*)([A-Za-z0-9_.:/#-]+)[)）]",
    re.IGNORECASE,
)
_NUMERIC_BIBLIOGRAPHY_REF_RE = re.compile(r"\d+(?:-\d+)*")
_NUMBER_RE = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?%?")
_NUMBER_UNIT_RE = re.compile(
    r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?\s*(?:Hz|kHz|rpm|r/min|rad/s|m/s2|m/s\^2|mm/s|m/s|N|kN|Pa|kPa|MPa|GPa|kg|g|s|ms|V|A|W|dB|%)\b",
    re.IGNORECASE,
)
_UNIT_RE = re.compile(r"\b(?:Hz|kHz|rpm|r/min|rad/s|m/s2|m/s\^2|mm/s|m/s|N|kN|Pa|kPa|MPa|GPa|kg|g|s|ms|V|A|W|dB)\b")
_SYMBOL_RE = re.compile(r"(?<![A-Za-z0-9_])(?:[ζωΩαβγλμξφ]|zeta|omega_n|omega_d|omega|fn|f_n|Q)(?![A-Za-z0-9_])")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "near",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}
_SUPPORT_GROUPS = {
    "damping_ratio": {"damping", "damping ratio", "zeta", "ζ", "阻尼", "阻尼比"},
    "higher": {"higher", "larger", "greater", "increased", "increase"},
    "improve": {"improves", "improve", "smooth", "smoother", "smoothly"},
    "runup": {"runup", "run-up", "passage", "passing", "traverse", "through"},
    "critical_speed": {"critical speed", "critical", "speed"},
}
_NEGATIVE_DIRECTIONS = {"reduce", "reduces", "reduced", "decrease", "decreases", "decreased", "lower", "lowers", "fall", "falls"}
_POSITIVE_DIRECTIONS = {"increase", "increases", "increased", "raise", "raises", "amplify", "amplifies", "higher"}
_QUANTITY_TERMS = (
    "critical speed",
    "shaft speed",
    "rotational speed",
    "running speed",
    "vibration speed",
    "damping ratio",
)
_UNSUPPORTED_SAFE_KEYS = (
    "task_id",
    "mode",
    "language",
    "answer_language",
    "query_language",
    "synthesis_mode",
    "token_cost",
    "cost",
    "evidence_count",
    "assets",
    "s4_analysis",
    "s5_derivation",
)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, SkillOutput):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    return {}


def _source_output(payload: SkillInput) -> Mapping[str, Any]:
    for key in ("s3_result", "skill_output", "upstream_result"):
        source = _as_mapping(payload.context.get(key))
        if source:
            return source
    return payload.context


def _structured(source: Mapping[str, Any]) -> Mapping[str, Any]:
    value = source.get("structured_result")
    return value if isinstance(value, Mapping) else source


def _s2_structured(payload: SkillInput) -> Mapping[str, Any]:
    s2_result = _as_mapping(payload.context.get("s2_result"))
    structured = s2_result.get("structured_result")
    return structured if isinstance(structured, Mapping) else s2_result


def _visible_rows(payload: SkillInput) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    structured = _s2_structured(payload)
    candidates = structured.get("evidence_context")
    if not isinstance(candidates, list):
        candidates = structured.get("retrieval_context")
    if isinstance(candidates, list):
        for row in candidates:
            if isinstance(row, Mapping) and row.get("chunk_id"):
                rows[str(row["chunk_id"])] = dict(row)

    retrieval_output = structured.get("retrieval_output")
    hits = retrieval_output.get("hits") if isinstance(retrieval_output, Mapping) else None
    if isinstance(hits, list):
        for hit in hits:
            if isinstance(hit, Mapping) and hit.get("chunk_id"):
                rows.setdefault(str(hit["chunk_id"]), dict(hit))
    return rows


def _source_citations(source: Mapping[str, Any], structured: Mapping[str, Any]) -> list[Citation]:
    citations: list[Citation] = []
    seen: set[str] = set()
    for container in (source, structured):
        raw = container.get("citations")
        if not isinstance(raw, list):
            continue
        for item in raw:
            try:
                citation = item if isinstance(item, Citation) else Citation.model_validate(item)
            except Exception:
                continue
            if citation.chunk_id not in seen:
                seen.add(citation.chunk_id)
                citations.append(citation)
    return citations


def _citation_from_claim(claim: Mapping[str, Any]) -> Citation | None:
    chunk_id = claim.get("chunk_id")
    doc_id = claim.get("doc_id")
    if not chunk_id or not doc_id:
        return None
    return Citation(
        chunk_id=str(chunk_id),
        doc_id=str(doc_id),
        pages=claim.get("pages") if isinstance(claim.get("pages"), list) else None,
        evidence_type=str(claim.get("evidence_type") or "documented"),
        confidence=float(claim.get("confidence", 1.0) or 1.0),
    )


def _claims(structured: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = structured.get("claims")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _derivation_steps(structured: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = structured.get("derivation_steps")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _visible_refs(answer: str) -> set[str]:
    bracket_refs = {
        reference
        for match in _REF_RE.finditer(answer or "")
        if not _NUMERIC_BIBLIOGRAPHY_REF_RE.fullmatch(reference := match.group(1))
    }
    return bracket_refs | {match.group(1) for match in _INLINE_EVIDENCE_REF_RE.finditer(answer or "")}


def _claim_tokens(text: str) -> set[str]:
    return {token for token in tokenize(text) if len(token) >= 4 and token not in _STOPWORDS}


def _evidence_text(row: Mapping[str, Any]) -> str:
    return str(row.get("text") or row.get("api_context") or "")


def _lexically_supported(claim_text: str, evidence_text: str) -> bool:
    claim_tokens = _claim_tokens(claim_text)
    if not claim_tokens:
        return True
    evidence_tokens = set(tokenize(evidence_text))
    if not evidence_tokens:
        return False
    if claim_tokens & evidence_tokens:
        return True
    return len(_support_groups(claim_text) & _support_groups(evidence_text)) >= 2


def _support_groups(text: str) -> set[str]:
    normalized = text.casefold()
    tokens = set(tokenize(text))
    groups: set[str] = set()
    for name, variants in _SUPPORT_GROUPS.items():
        for variant in variants:
            if " " in variant:
                if variant in normalized:
                    groups.add(name)
                    break
            elif variant.casefold() in tokens or variant in text:
                groups.add(name)
                break
    return groups


def _direction_conflicts(claim_text: str, evidence_text: str) -> list[str]:
    claim_tokens = set(tokenize(claim_text))
    claim_positive = bool(claim_tokens & _POSITIVE_DIRECTIONS)
    claim_negative = bool(claim_tokens & _NEGATIVE_DIRECTIONS)
    if not claim_positive and not claim_negative:
        return []
    claim_anchors = _direction_anchor_tokens(claim_text)
    matching_evidence_directions = _matching_evidence_directions(evidence_text, claim_anchors)
    evidence_positive = "positive" in matching_evidence_directions
    evidence_negative = "negative" in matching_evidence_directions
    if claim_positive and evidence_positive:
        return []
    if claim_negative and evidence_negative:
        return []
    if claim_positive and evidence_negative:
        return ["claim direction is positive but cited evidence direction is negative"]
    if claim_negative and evidence_positive:
        return ["claim direction is negative but cited evidence direction is positive"]
    return []


def _direction_anchor_tokens(text: str) -> set[str]:
    direction_terms = _POSITIVE_DIRECTIONS | _NEGATIVE_DIRECTIONS
    return {
        token
        for token in _claim_tokens(text)
        if token not in direction_terms
    }


def _matching_evidence_directions(evidence_text: str, claim_anchors: set[str]) -> set[str]:
    directions: set[str] = set()
    for clause in _direction_clauses(evidence_text):
        clause_tokens = set(tokenize(clause))
        if len(claim_anchors & clause_tokens) < 2:
            continue
        if clause_tokens & _POSITIVE_DIRECTIONS:
            directions.add("positive")
        if clause_tokens & _NEGATIVE_DIRECTIONS:
            directions.add("negative")
    return directions


def _direction_clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[.;,，。；]|(?:\bbut\b)", text, flags=re.IGNORECASE) if part.strip()]


def _quantity_context_conflicts(claim_text: str, evidence_text: str) -> list[str]:
    claim_compact = re.sub(r"\s+", " ", claim_text).casefold()
    evidence_compact = re.sub(r"\s+", " ", evidence_text).casefold()
    conflicts: list[str] = []
    for value in _number_unit_values(claim_text):
        if value not in _number_unit_values(evidence_text):
            continue
        claim_terms = {term for term in _QUANTITY_TERMS if term in claim_compact}
        evidence_terms = {term for term in _QUANTITY_TERMS if term in evidence_compact}
        missing_terms = sorted(term for term in claim_terms if term not in evidence_terms)
        if missing_terms and evidence_terms:
            conflicts.append(
                "claim binds "
                + value
                + " to unsupported quantity term(s): "
                + ", ".join(missing_terms)
            )
    return conflicts


def _number_unit_values(text: str) -> set[str]:
    return {_normalize_significant_item(match.group(0)) for match in _NUMBER_UNIT_RE.finditer(text)}


def _significant_items(text: str) -> set[str]:
    items: set[str] = set()
    for pattern in (_NUMBER_UNIT_RE, _NUMBER_RE, _UNIT_RE, _SYMBOL_RE):
        for match in pattern.finditer(text):
            items.add(_normalize_significant_item(match.group(0)))
    return {item for item in items if item}


def _normalize_significant_item(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _missing_significant_items(claim_text: str, evidence_text: str) -> list[str]:
    claim_items = _significant_items(claim_text)
    if not claim_items:
        return []
    evidence_items = _significant_items(evidence_text)
    evidence_compact = re.sub(r"\s+", "", evidence_text).casefold()
    missing = sorted(item for item in claim_items if item not in evidence_items and item not in evidence_compact)
    return missing


def _deterministic_support_conflicts(claim_text: str, evidence_text: str) -> list[str]:
    return [
        *_direction_conflicts(claim_text, evidence_text),
        *_quantity_context_conflicts(claim_text, evidence_text),
    ]


def _unsupported(
    claim: Mapping[str, Any],
    *,
    visible_rows: Mapping[str, Mapping[str, Any]],
    visible_refs: set[str],
    require_visible_ref: bool,
    strict_llm_support: bool,
) -> dict[str, Any] | None:
    claim_text = str(claim.get("text") or "")
    chunk_id = str(claim.get("chunk_id") or "")
    reasons: list[str] = []
    if not chunk_id:
        reasons.append("missing chunk_id")
    elif chunk_id not in visible_rows:
        reasons.append("chunk not visible in retrieval")
    elif require_visible_ref and chunk_id not in visible_refs:
        reasons.append("claim missing visible [chunk_id] reference")
    else:
        evidence = _evidence_text(visible_rows[chunk_id])
        if not _lexically_supported(claim_text, evidence):
            reasons.append("claim text does not lexically match cited evidence")
        if strict_llm_support:
            support_conflicts = _deterministic_support_conflicts(claim_text, evidence)
            reasons.extend(support_conflicts)
            missing_items = _missing_significant_items(claim_text, evidence)
            if missing_items:
                reasons.append(
                    "LLM claim contains number/unit/symbol not found in cited evidence: "
                    + ", ".join(missing_items)
                )

    if not reasons:
        return None
    return {"claim": claim_text, "chunk_id": chunk_id or None, "reasons": reasons}


def _unsupported_derivation_step(
    step: Mapping[str, Any],
    *,
    visible_rows: Mapping[str, Mapping[str, Any]],
    strict_llm_support: bool,
) -> dict[str, Any] | None:
    source_type = step.get("source_type")
    if source_type == "axiomatic":
        return None
    step_id = str(step.get("id") or "")
    step_text = str(step.get("text") or "")
    chunk_id = str(step.get("chunk_id") or "")
    reasons: list[str] = []
    if source_type != "evidence":
        reasons.append("derivation step source_type must be evidence or axiomatic")
    if not chunk_id:
        reasons.append("evidence derivation step missing chunk_id")
    elif chunk_id not in visible_rows:
        reasons.append("evidence derivation step chunk not visible in retrieval")
    elif strict_llm_support:
        evidence = _evidence_text(visible_rows[chunk_id])
        missing_items = _missing_significant_items(step_text, evidence)
        if missing_items:
            reasons.append(
                "LLM derivation step contains number/unit/symbol not found in cited evidence: "
                + ", ".join(missing_items)
            )
    if reasons:
        return {"claim": step_text, "chunk_id": chunk_id or None, "step_id": step_id or None, "reasons": reasons}
    return None


def _answer_has_uncited_claim(answer: str, claims: list[Mapping[str, Any]]) -> bool:
    # V2 needs structured claims to verify visibility and lexical support. A
    # bare answer with bracket refs is still not machine-checkable here.
    return bool(answer.strip()) and not claims


def _blocked_result(
    structured: Mapping[str, Any],
    *,
    supported_claims: list[dict[str, Any]],
    unsupported: list[dict[str, Any]],
    visible_rows: Mapping[str, Mapping[str, Any]],
    refs: set[str],
    derivation_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    checked = {key: structured[key] for key in _UNSUPPORTED_SAFE_KEYS if key in structured}
    checked.update(
        {
            "answer": "",
            "claims": supported_claims,
            "unsupported_claims": unsupported,
            "citation_check": {
                "visible_chunk_ids": sorted(visible_rows),
                "visible_answer_refs": sorted(refs),
                "unsupported_count": len(unsupported),
                "derivation_step_count": len(derivation_steps),
            },
        }
    )
    return checked


class CitationCheckSkill(Skill):
    name = "v2_citation_check"

    def run(self, payload: SkillInput) -> SkillOutput:
        source = _source_output(payload)
        structured = dict(_structured(source))
        answer = str(structured.get("answer") or source.get("answer") or "")
        claims = _claims(structured)
        derivation_steps = _derivation_steps(structured)
        visible_rows = _visible_rows(payload)
        refs = _visible_refs(answer)
        require_visible_ref = structured.get("synthesis_mode") == "llm"
        strict_llm_support = structured.get("synthesis_mode") == "llm"

        unsupported: list[dict[str, Any]] = []
        supported_claims: list[dict[str, Any]] = []
        for claim in claims:
            issue = _unsupported(
                claim,
                visible_rows=visible_rows,
                visible_refs=refs,
                require_visible_ref=require_visible_ref,
                strict_llm_support=strict_llm_support,
            )
            if issue:
                unsupported.append(issue)
            else:
                supported_claims.append(claim)

        for ref in sorted(refs - set(visible_rows)):
            unsupported.append({"claim": "", "chunk_id": ref, "reasons": ["referenced chunk not visible in retrieval"]})

        for step in derivation_steps:
            issue = _unsupported_derivation_step(step, visible_rows=visible_rows, strict_llm_support=strict_llm_support)
            if issue:
                unsupported.append(issue)

        if _answer_has_uncited_claim(answer, claims):
            unsupported.append({"claim": answer.strip(), "chunk_id": None, "reasons": ["answer contains unstructured claim"]})

        citations_by_chunk = {citation.chunk_id: citation for citation in _source_citations(source, structured)}
        supported_citations: list[Citation] = []
        for claim in supported_claims:
            chunk_id = str(claim.get("chunk_id"))
            citation = citations_by_chunk.get(chunk_id) or _citation_from_claim(claim)
            if citation and citation.chunk_id not in {item.chunk_id for item in supported_citations}:
                supported_citations.append(citation)
        # Retain a citation for every referenced, S2-visible chunk so deterministic
        # inline evidence tags stay aligned -- but only when the answer is not
        # blocked. A faithfulness-blocked (insufficient) answer must not surface
        # supporting citations (frozen V2 contract).
        if not unsupported:
            cited_ids = {item.chunk_id for item in supported_citations}
            for chunk_id in sorted(refs):
                row = visible_rows.get(chunk_id)
                if row is not None and chunk_id not in cited_ids:
                    supported_citations.append(citation_from_evidence(row))
                    cited_ids.add(chunk_id)

        checked = {
            **structured,
            "claims": supported_claims,
            "unsupported_claims": unsupported,
            "citation_check": {
                "visible_chunk_ids": sorted(visible_rows),
                "visible_answer_refs": sorted(refs),
                "unsupported_count": len(unsupported),
                "derivation_step_count": len(derivation_steps),
            },
        }
        warnings = list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []

        if unsupported:
            checked = _blocked_result(
                structured,
                supported_claims=supported_claims,
                unsupported=unsupported,
                visible_rows=visible_rows,
                refs=refs,
                derivation_steps=derivation_steps,
            )
            warnings.append(f"V2 blocked {len(unsupported)} unsupported claim(s).")
            return SkillOutput(
                status="insufficient",
                summary=f"V2 citation check blocked {len(unsupported)} unsupported claim(s).",
                structured_result=checked,
                citations=supported_citations,
                warnings=warnings,
                handoff_recommendation="Revise unsupported claims or broaden retrieval evidence.",
            )

        return SkillOutput(
            status="ok",
            summary=f"V2 citation check ok: {len(supported_claims)} claim(s).",
            structured_result=checked,
            citations=supported_citations,
            warnings=warnings,
            handoff_recommendation="Pass checked answer to V4.",
        )
