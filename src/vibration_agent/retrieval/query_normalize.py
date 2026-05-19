"""Query normalization for Phase-0 retrieval.

Phase-0 keeps this deterministic and local: normalize whitespace/case, add a small
engineering synonym layer, and infer the broad retrieval intent. The taxonomy YAML
files remain the durable long-term source, but this module must also work when the
local seed taxonomy is sparse or partially corrupted.
"""
from __future__ import annotations

import re
from typing import Any

from vibration_agent.schemas import Intent

_DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "damping_ratio": ("damping ratio", "zeta", "ζ", "阻尼比", "相对阻尼"),
    "natural_frequency": ("natural frequency", "omega_n", "ωn", "固有频率", "自然频率"),
    "critical_speed": ("critical speed", "临界转速", "临界速度"),
    "rotor_unbalance": ("rotor unbalance", "unbalance", "不平衡", "转子不平衡"),
    "orbit": ("orbit", "shaft orbit", "轴心轨迹", "转子轨迹"),
    "synchronous_response": ("synchronous response", "1x", "一倍频", "同步响应"),
    "misalignment": ("misalignment", "不对中", "轴系不对中"),
    "bearing_fault": ("bearing fault", "轴承故障", "bearing defect"),
}

_SYMBOL_ALIASES: dict[str, tuple[str, ...]] = {
    "zeta": ("zeta", "ζ", "damping ratio", "阻尼比"),
    "omega_n": ("omega_n", "ωn", "natural frequency", "固有频率"),
    "omega_d": ("omega_d", "ωd", "damped natural frequency", "阻尼固有频率"),
    "Q": ("Q", "quality factor", "品质因数"),
}


def _clean_query(query: str) -> str:
    return re.sub(r"\s+", " ", query).strip()


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def infer_intent(query: str) -> Intent:
    lowered = query.lower()
    if any(marker in lowered for marker in ("define", "definition", "what is", "是什么", "定义")):
        return "definition"
    if any(marker in lowered for marker in ("compare", "difference", " vs ", "versus", "区别", "对比", "比较")):
        return "comparison"
    if any(marker in lowered for marker in ("standard", "iso", "api ", "gb/t", "规范", "标准")):
        return "standard_lookup"
    if any(marker in lowered for marker in ("summary", "summarize", "总结", "概述", "摘要")):
        return "summary"
    if lowered:
        return "engineering"
    return "unknown"


def normalize(query: str) -> dict[str, Any]:
    """Return normalized query metadata used by retrieval lanes."""
    cleaned = _clean_query(query)
    detected_terms = [term for term, aliases in _DOMAIN_ALIASES.items() if _contains_any(cleaned, aliases)]
    detected_symbols = [symbol for symbol, aliases in _SYMBOL_ALIASES.items() if _contains_any(cleaned, aliases)]

    expansions: list[str] = []
    for term in detected_terms:
        expansions.extend(_DOMAIN_ALIASES[term])
    for symbol in detected_symbols:
        expansions.extend(_SYMBOL_ALIASES[symbol])

    expanded = " ".join(dict.fromkeys([cleaned, *expansions])) if cleaned else ""
    return {
        "normalized_query": expanded,
        "original_query": query,
        "detected_terms": detected_terms,
        "detected_symbols": detected_symbols,
        "intent_hint": infer_intent(cleaned),
    }
