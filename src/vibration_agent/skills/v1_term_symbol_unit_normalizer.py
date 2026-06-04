"""V1 term/symbol/unit normalization.

V1 is an optional deterministic quality layer. It normalizes in-memory S3 input
and the final V4 answer without changing citation anchors or source files.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibration_agent.schemas import SkillInput, SkillOutput

from .base import Skill

_ANCHOR_RE = re.compile(r"(\[[^\]]+\])")


@dataclass(frozen=True)
class _Rule:
    alias: str
    kind: str
    canonical_en: str
    canonical_zh: str | None = None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_yaml(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def _term_rules(taxonomy_dir: Path) -> list[_Rule]:
    entries = _read_yaml(taxonomy_dir / "terms_zh_en.yaml") or _read_yaml(taxonomy_dir / "glossary_zh_en.yaml")
    rules: list[_Rule] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        canonical_en = str(entry.get("canonical_en") or entry.get("canonical") or entry.get("display") or entry.get("term") or "").strip()
        canonical_zh = str(entry.get("canonical_zh") or entry.get("zh") or "").strip() or None
        if not canonical_en:
            continue
        aliases = [*(_list(entry.get("aliases"))), *_list(entry.get("zh")), *_list(entry.get("en")), *_list(entry.get("symbol"))]
        for alias in aliases:
            if alias.strip():
                rules.append(
                    _Rule(
                        alias=alias.strip(),
                        kind="term",
                        canonical_en=canonical_en,
                        canonical_zh=canonical_zh,
                    )
                )
    return rules


def _unit_rules(taxonomy_dir: Path) -> list[_Rule]:
    entries = _read_yaml(taxonomy_dir / "units.yaml")
    rules: list[_Rule] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        canonical = str(entry.get("canonical_units") or entry.get("unit") or "").strip()
        if not canonical:
            continue
        # `aliases` may contain engineering-unit conversions such as mm/s -> m/s.
        # Obj11 only normalizes SI spelling variants, so use normalize_aliases.
        for alias in _list(entry.get("normalize_aliases")):
            if alias.strip() and alias.casefold() != canonical.casefold():
                rules.append(_Rule(alias=alias.strip(), kind="unit", canonical_en=canonical))
    return rules


def _default_rules() -> list[_Rule]:
    return [
        _Rule("damping factor", "term", "damping ratio", "阻尼比"),
        _Rule("zeta", "term", "damping ratio", "阻尼比"),
        _Rule("critical velocity", "term", "critical speed", "临界转速"),
        _Rule("Hertz", "unit", "Hz"),
        _Rule("hertz", "unit", "Hz"),
        _Rule("cycles per second", "unit", "Hz"),
        _Rule("rad/sec", "unit", "rad/s"),
    ]


def _pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if all(char.isascii() and (char.isalnum() or char in {"_", " ", "/", "-", "."}) for char in alias):
        return re.compile(r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])", flags=re.IGNORECASE)
    return re.compile(escaped)


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def _canonical_for(rule: _Rule, text: str) -> str:
    if rule.kind == "term" and _has_cjk(text) and rule.canonical_zh:
        return rule.canonical_zh
    return rule.canonical_en


class TermSymbolUnitNormalizerSkill(Skill):
    name = "v1_term_symbol_unit_normalizer"

    def __init__(self, *, taxonomy_dir: str | Path | None = None) -> None:
        self._taxonomy_dir = Path(taxonomy_dir) if taxonomy_dir is not None else _project_root() / "taxonomy"
        rules = [*_term_rules(self._taxonomy_dir), *_unit_rules(self._taxonomy_dir)]
        self._rules = sorted(rules or _default_rules(), key=lambda rule: len(rule.alias), reverse=True)

    def normalize_text(self, text: str) -> tuple[str, list[dict[str, str]]]:
        replacements: list[dict[str, str]] = []
        parts = _ANCHOR_RE.split(text)
        for index, part in enumerate(parts):
            if not part or _ANCHOR_RE.fullmatch(part):
                continue
            updated = part
            for rule in self._rules:
                pattern = _pattern(rule.alias)
                canonical = _canonical_for(rule, updated)

                def _replace(match: re.Match[str]) -> str:
                    if match.group(0).casefold() == canonical.casefold():
                        return match.group(0)
                    replacements.append({"from": match.group(0), "to": canonical, "kind": rule.kind})
                    return canonical

                updated = pattern.sub(_replace, updated)
            parts[index] = updated
        return "".join(parts), replacements

    def normalize_s2_result(self, s2_result: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
        normalized = copy.deepcopy(s2_result)
        replacements: list[dict[str, str]] = []
        structured = normalized.get("structured_result") if isinstance(normalized.get("structured_result"), dict) else normalized
        rows = structured.get("retrieval_context") if isinstance(structured, dict) else None
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("text", "api_context"):
                    if isinstance(row.get(key), str):
                        row[key], row_replacements = self.normalize_text(row[key])
                        replacements.extend(row_replacements)
        return normalized, replacements

    def normalize_skill_output(self, output: SkillOutput) -> tuple[SkillOutput, list[dict[str, str]]]:
        data = output.model_dump(mode="python")
        structured = data.get("structured_result") if isinstance(data.get("structured_result"), dict) else {}
        replacements: list[dict[str, str]] = []
        if isinstance(structured.get("answer"), str):
            structured["answer"], answer_replacements = self.normalize_text(structured["answer"])
            replacements.extend(answer_replacements)
        sections = structured.get("sections")
        if isinstance(sections, dict):
            for key, value in list(sections.items()):
                if isinstance(value, str):
                    sections[key], section_replacements = self.normalize_text(value)
                    replacements.extend(section_replacements)
        data["structured_result"] = structured
        return SkillOutput.model_validate(data), replacements

    def run(self, payload: SkillInput) -> SkillOutput:
        text = str(payload.context.get("text") or payload.context.get("answer") or "")
        normalized, replacements = self.normalize_text(text)
        return SkillOutput(
            status="ok",
            summary=f"V1 normalization ok: {len(replacements)} replacement(s).",
            structured_result={
                "task_id": payload.task_id,
                "normalized_text": normalized,
                "replacements": replacements,
            },
            warnings=[],
            handoff_recommendation="Use normalized_text at the requested call point.",
        )
