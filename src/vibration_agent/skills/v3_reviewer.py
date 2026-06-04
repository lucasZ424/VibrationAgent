"""V3 advisory reviewer.

V3 runs after V4 for extreme tasks. It checks answer structure and obvious
quality risks, then returns reviewer notes without blocking the final answer.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from vibration_agent.retrieval.bm25 import tokenize
from vibration_agent.schemas import SkillInput, SkillOutput

from .base import Skill

_SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "conclusion": ("conclusion", "结论"),
    "evidence": ("evidence", "证据"),
    "limits": (
        "limitations",
        "limits",
        "failure_modes",
        "caveats",
        "premises",
        "限制",
        "适用前提",
        "失效条件",
        "常见误区",
        "失效条件/常见误区",
    ),
}
_OVERCLAIM_PATTERNS: tuple[str, ...] = (
    r"\balways\b",
    r"\bnever\b",
    r"\bguarantee[sd]?\b",
    r"\bprove[sd]?\b",
    r"\beliminate[sd]?\b",
    r"\bno risk\b",
    "绝对",
    "必然",
    "一定",
    "永远",
    "从不",
    "证明",
    "消除",
    "没有风险",
)
_STOP_TOKENS = {
    "what",
    "why",
    "how",
    "does",
    "with",
    "from",
    "about",
    "explain",
    "effect",
    "影响",
    "如何",
    "什么",
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, SkillOutput):
        return value.model_dump(mode="python")
    if isinstance(value, Mapping):
        return value
    return {}


def _source_payload(payload: SkillInput) -> Mapping[str, Any]:
    for key in ("upstream_result", "v4_result", "skill_output"):
        source = _as_mapping(payload.context.get(key))
        if source:
            return source
    return payload.context


def _structured(source: Mapping[str, Any]) -> Mapping[str, Any]:
    value = source.get("structured_result")
    return value if isinstance(value, Mapping) else source


def _answer_text(source: Mapping[str, Any], structured: Mapping[str, Any]) -> str:
    for value in (structured.get("answer"), source.get("answer"), source.get("summary")):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _sections(structured: Mapping[str, Any]) -> Mapping[str, Any]:
    sections = structured.get("sections")
    return sections if isinstance(sections, Mapping) else {}


def _has_section(structured: Mapping[str, Any], answer: str, key: str) -> bool:
    sections = _sections(structured)
    for alias in _SECTION_ALIASES[key]:
        value = structured.get(alias) or sections.get(alias)
        if isinstance(value, str) and value.strip():
            return True
    section_keys = structured.get("section_keys")
    if isinstance(section_keys, list) and any(str(item) in _SECTION_ALIASES[key] for item in section_keys):
        return True
    return any(f"## {alias}" in answer for alias in _SECTION_ALIASES[key])


def _query_tokens(query: str) -> set[str]:
    return {token for token in tokenize(query) if len(token) >= 3 and token not in _STOP_TOKENS}


def _answer_tokens(answer: str) -> set[str]:
    return {token for token in tokenize(answer) if len(token) >= 3 and token not in _STOP_TOKENS}


def _is_off_topic(query: str, answer: str) -> bool:
    query_terms = _query_tokens(query)
    if not query_terms:
        return False
    return not bool(query_terms & _answer_tokens(answer))


def _overclaims(answer: str) -> list[str]:
    issues: list[str] = []
    for pattern in _OVERCLAIM_PATTERNS:
        if re.search(pattern, answer, flags=re.IGNORECASE):
            issues.append(pattern)
    return issues


class ReviewerSkill(Skill):
    name = "v3_reviewer"

    def run(self, payload: SkillInput) -> SkillOutput:
        source = _source_payload(payload)
        structured = _structured(source)
        answer = _answer_text(source, structured)
        notes: list[dict[str, str]] = []

        for key, label in (
            ("conclusion", "missing_conclusion"),
            ("evidence", "missing_evidence"),
            ("limits", "missing_limits"),
        ):
            if not _has_section(structured, answer, key):
                notes.append(
                    {
                        "code": label,
                        "message": f"V3 expected a {key} section for an extreme-task answer.",
                    }
                )

        if answer and _is_off_topic(payload.user_query, answer):
            notes.append(
                {
                    "code": "off_topic",
                    "message": "Answer text does not share reviewer-visible topic terms with the user query.",
                }
            )

        risky_patterns = _overclaims(answer)
        if risky_patterns:
            notes.append(
                {
                    "code": "overclaiming",
                    "message": "Answer contains absolute or proof-like wording that may overstate evidence support.",
                }
            )

        result = {
            "task_id": payload.task_id,
            "reviewer_notes": notes,
            "review_summary": {
                "issue_count": len(notes),
                "checked_sections": ["conclusion", "evidence", "limits"],
                "checked_answer_relevance": True,
                "checked_overclaiming": True,
            },
        }
        warnings = list(source.get("warnings") or []) if isinstance(source.get("warnings"), list) else []

        if notes:
            return SkillOutput(
                status="insufficient",
                summary=f"V3 reviewer flagged {len(notes)} issue(s).",
                structured_result=result,
                citations=list(source.get("citations") or []),
                warnings=warnings,
                handoff_recommendation="Review the advisory notes before supervisor escalation or release.",
            )

        return SkillOutput(
            status="ok",
            summary="V3 reviewer ok: no advisory issues.",
            structured_result=result,
            citations=list(source.get("citations") or []),
            warnings=warnings,
            handoff_recommendation="Return answer; no V3 advisory issue found.",
        )
