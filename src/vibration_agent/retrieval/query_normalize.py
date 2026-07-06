"""Query normalization for Phase-0 retrieval.

Phase-0 keeps this deterministic and local: normalize whitespace/case, add a small
engineering synonym layer, and infer the broad retrieval intent. The taxonomy YAML
files remain the durable long-term source, but this module must also work when the
local seed taxonomy is sparse or partially corrupted.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from vibration_agent.schemas import Intent

_ALIAS_PATH = Path(__file__).resolve().parents[3] / "taxonomy" / "retrieval_aliases.yaml"
_ALIAS_SCHEMA = "phase5.retrieval_aliases.v1"
_STANDARD_CATALOG_PATH = Path(__file__).resolve().parents[3] / "taxonomy" / "corpus_standards.yaml"
_STANDARD_CATALOG_SCHEMA = "phase5.corpus_standards.v1"

_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "zeta": ("zeta", "ζ", "damping ratio", "阻尼比"),
    "omega_n": ("omega_n", "ωn", "natural frequency", "固有频率"),
    "omega_d": ("omega_d", "ωd", "damped natural frequency", "阻尼固有频率"),
    "Q": ("Q", "quality factor", "品质因数"),
}

_STANDARD_MARKERS = ("standard", "iso", "api ", "gb/t", "规范", "标准")
_SCOPE_MARKERS = ("scope", "适用范围", "范围", "适用于")
_OUTCOME_MARKERS = ("发生什么", "会怎样", "如何变化", "什么影响", "what happens", "affect", "effect")
_CRITICAL_SPEED_OUTCOME_EXPANSIONS = ("响应放大", "振幅增大", "振动增大", "response amplification", "amplitude increase")


@lru_cache(maxsize=8)
def load_alias_families(path: str | Path = _ALIAS_PATH) -> dict[str, tuple[str, ...]]:
    source = Path(path)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != _ALIAS_SCHEMA:
        raise ValueError(f"Unsupported retrieval alias taxonomy: {source}")
    families: dict[str, tuple[str, ...]] = {}
    for row in data.get("families", []):
        if not isinstance(row, dict) or not row.get("id") or not isinstance(row.get("aliases"), list):
            raise ValueError(f"Invalid retrieval alias family in {source}")
        source_aliases = row.get("retrieval_aliases") if isinstance(row.get("retrieval_aliases"), list) else row["aliases"]
        aliases = tuple(str(value).strip() for value in source_aliases if str(value).strip())
        if len(aliases) < 2:
            raise ValueError(f"Retrieval alias family requires at least two aliases: {row.get('id')}")
        families[str(row["id"])] = aliases
    return families


def clear_alias_cache() -> None:
    load_alias_families.cache_clear()


def _standard_keys(value: str) -> tuple[tuple[str, str], ...]:
    matches = re.finditer(
        r"(?i)(gb\s*[/∕]?\s*t|gbt|dl\s*[/∕]?\s*t|dlt|iso|api)[\s_-]*(\d{3,6})(?:\.\d+)*",
        value,
    )
    return tuple(
        (re.sub(r"[\s/∕]", "", match.group(1)).casefold(), match.group(2))
        for match in matches
    )


def _standard_key(value: str) -> tuple[str, str] | None:
    return next(iter(_standard_keys(value)), None)


def standard_identifiers_from_sources(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Extract standard families from ingested document identity fields only."""

    identifiers: set[tuple[str, str]] = set()
    for row in rows:
        for field in ("source_title", "source_filename", "doc_id", "title"):
            identifiers.update(_standard_keys(str(row.get(field) or "")))
    names = {"gbt": "GB/T", "dlt": "DL/T", "iso": "ISO", "api": "API"}
    return tuple(f"{names[organization]} {number}" for organization, number in sorted(identifiers))


@lru_cache(maxsize=4)
def load_corpus_standard_identifiers(path: str | Path = _STANDARD_CATALOG_PATH) -> frozenset[str]:
    source = Path(path)
    payload = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != _STANDARD_CATALOG_SCHEMA:
        raise ValueError(f"Unsupported corpus standard catalog: {source}")
    identifiers = payload.get("identifiers")
    if not isinstance(identifiers, list):
        raise ValueError(f"Invalid corpus standard catalog: {source}")
    keys = {_standard_key(str(value)) for value in identifiers}
    if None in keys:
        raise ValueError(f"Invalid standard identifier in corpus catalog: {source}")
    return frozenset(":".join(key) for key in keys if key is not None)


def is_corpus_standard_query(query: str) -> bool:
    key = _standard_key(query)
    return key is not None and ":".join(key) in load_corpus_standard_identifiers()


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def alias_family_coverage(query: str, answer: str) -> tuple[int, int]:
    """Return (covered, total) domain-term families for language-agnostic coverage.

    A term family present in the query (via any alias) counts as covered when any
    alias of the same family appears in the answer. Because the alias families are
    bilingual, this lets an English query be scored as covered by a Chinese answer
    (and vice versa), where raw token overlap would read zero.
    """
    query_lower = query.lower()
    answer_lower = answer.lower()
    covered = 0
    total = 0
    for aliases in load_alias_families().values():
        if any(alias.lower() in query_lower for alias in aliases):
            total += 1
            if any(alias.lower() in answer_lower for alias in aliases):
                covered += 1
    return covered, total


def is_standard_scope_query(query: str) -> bool:
    lowered = query.lower()
    return any(marker in lowered for marker in _STANDARD_MARKERS) and any(
        marker in lowered for marker in _SCOPE_MARKERS
    )


def focus_aliases(query: str) -> tuple[str, ...]:
    """Return the alias family with the longest member present in the query."""
    lowered = _clean_query(query).lower()
    matches: list[tuple[int, tuple[str, ...]]] = []
    for aliases in load_alias_families().values():
        matched_lengths = [len(alias) for alias in aliases if alias.lower() in lowered]
        if matched_lengths:
            matches.append((max(matched_lengths), aliases))
    return max(matches, key=lambda item: item[0])[1] if matches else ()


def infer_intent(query: str) -> Intent:
    lowered = query.lower()
    if is_standard_scope_query(query) or any(marker in lowered for marker in _STANDARD_MARKERS):
        return "standard_lookup"
    if any(marker in lowered for marker in ("define", "definition", "what is", "是什么", "定义")):
        return "definition"
    if any(marker in lowered for marker in ("compare", "difference", " vs ", "versus", "区别", "对比", "比较")):
        return "comparison"
    if any(marker in lowered for marker in ("summary", "summarize", "总结", "概述", "摘要")):
        return "summary"
    if lowered:
        return "engineering"
    return "unknown"


def normalize(query: str) -> dict[str, Any]:
    """Return normalized query metadata used by retrieval lanes."""
    cleaned = _clean_query(query)
    domain_aliases = load_alias_families()
    detected_terms = [term for term, aliases in domain_aliases.items() if _contains_any(cleaned, aliases)]
    detected_symbols = [symbol for symbol, aliases in _SYMBOL_ALIASES.items() if _contains_any(cleaned, aliases)]

    expansions: list[str] = []
    for term in detected_terms:
        expansions.extend(domain_aliases[term])
    for symbol in detected_symbols:
        expansions.extend(_SYMBOL_ALIASES[symbol])
    if "critical_speed" in detected_terms and _contains_any(cleaned, _OUTCOME_MARKERS):
        expansions.extend(_CRITICAL_SPEED_OUTCOME_EXPANSIONS)

    expanded = " ".join(dict.fromkeys([cleaned, *expansions])) if cleaned else ""
    return {
        "normalized_query": expanded,
        "semantic_query": cleaned,
        "original_query": query,
        "detected_terms": detected_terms,
        "detected_symbols": detected_symbols,
        "alias_schema_version": _ALIAS_SCHEMA,
        "intent_hint": infer_intent(cleaned),
    }
