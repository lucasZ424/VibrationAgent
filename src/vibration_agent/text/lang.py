"""Deterministic language detection shared by answer skills."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _language_hint(item: Mapping[str, Any]) -> str | None:
    for key in ("language", "doc_language", "source_language"):
        value = item.get(key)
        if value in {"zh", "en"}:
            return str(value)
    metadata = item.get("metadata")
    if isinstance(metadata, Mapping):
        for key in ("language", "doc_language", "source_language"):
            value = metadata.get(key)
            if value in {"zh", "en"}:
                return str(value)
    return None


def dominant_language(items: Iterable[Mapping[str, Any] | str]) -> str:
    values = list(items)
    hints = [_language_hint(item) for item in values if isinstance(item, Mapping)]
    if hints.count("zh") > hints.count("en"):
        return "zh"
    if hints.count("en") > hints.count("zh"):
        return "en"

    text = "\n".join(
        str(item.get("text") or "") if isinstance(item, Mapping) else str(item)
        for item in values
    )
    cjk = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    latin = sum(1 for char in text if char.isascii() and char.isalpha())
    return "zh" if cjk >= latin else "en"
