"""Formula rendering contract helpers shared by S5 and V4."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any
from xml.etree import ElementTree

from pydantic import ValidationError

from vibration_agent.schemas import FormulaRender


def _clean_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _metadata(asset: Mapping[str, Any]) -> Mapping[str, Any]:
    value = asset.get("metadata")
    return value if isinstance(value, Mapping) else {}


def _first_text(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _latex_warnings(value: str) -> list[str]:
    if not value:
        return []
    warnings: list[str] = []
    depth = 0
    escaped = False
    for char in value:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            if depth == 0:
                return ["invalid LaTeX formula markup: unmatched closing brace."]
            depth -= 1
    if depth:
        return ["invalid LaTeX formula markup: unmatched opening brace."]
    warnings.extend(_latex_frac_warnings(value))
    warnings.extend(_latex_environment_warnings(value))
    return warnings


def _read_braced_arg(value: str, start: int) -> int | None:
    index = start
    while index < len(value) and value[index].isspace():
        index += 1
    if index >= len(value) or value[index] != "{":
        return None

    depth = 0
    escaped = False
    for current in range(index, len(value)):
        char = value[current]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return current + 1
    return None


def _latex_frac_warnings(value: str) -> list[str]:
    warnings: list[str] = []
    index = 0
    while True:
        index = value.find(r"\frac", index)
        if index == -1:
            return warnings
        next_index = index + len(r"\frac")
        if next_index < len(value) and value[next_index].isalpha():
            index = next_index
            continue
        numerator_end = _read_braced_arg(value, next_index)
        denominator_end = _read_braced_arg(value, numerator_end) if numerator_end is not None else None
        if numerator_end is None or denominator_end is None:
            warnings.append(r"invalid LaTeX formula markup: \frac must have two braced arguments.")
        index = next_index


def _latex_environment_warnings(value: str) -> list[str]:
    warnings: list[str] = []
    stack: list[str] = []
    for match in re.finditer(r"\\(begin|end)\s*\{([^{}]+)\}", value):
        command = match.group(1)
        environment = match.group(2).strip()
        if command == "begin":
            stack.append(environment)
            continue
        if not stack:
            warnings.append(f"invalid LaTeX formula markup: unmatched \\end{{{environment}}}.")
            continue
        expected = stack.pop()
        if expected != environment:
            warnings.append(
                f"invalid LaTeX formula markup: \\begin{{{expected}}} closed by \\end{{{environment}}}."
            )
    for environment in reversed(stack):
        warnings.append(f"invalid LaTeX formula markup: missing \\end{{{environment}}}.")
    return warnings


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _mathml_warnings(value: str) -> list[str]:
    if not value:
        return []
    try:
        root = ElementTree.fromstring(value)
    except ElementTree.ParseError as exc:
        return [f"invalid MathML formula markup: {exc}."]
    if _local_name(root.tag) != "math":
        return ["invalid MathML formula markup: root element must be <math>."]
    return []


def formula_render_from_asset(asset: Mapping[str, Any], *, index: int = 1) -> tuple[dict[str, Any] | None, list[str]]:
    if asset.get("object_type") != "formula":
        return None, []
    metadata = _metadata(asset)
    asset_id = _clean_text(asset.get("asset_id"))
    formula_id = asset_id or f"formula_{index}"
    latex = _first_text(asset.get("latex"), asset.get("latex_markup"), metadata.get("latex"), metadata.get("latex_markup"))
    mathml = _first_text(asset.get("mathml"), metadata.get("mathml"))
    plain_text = _first_text(asset.get("plain_text"), asset.get("text_preview"), asset.get("text"), latex, mathml)
    if not plain_text:
        return None, [f"formula render {formula_id} omitted: no plain-text fallback is available."]

    warnings = [*_latex_warnings(latex), *_mathml_warnings(mathml)]
    status = "renderable" if latex or mathml else "plain_text_fallback"
    if warnings:
        status = "invalid_markup"
        latex = None
        mathml = None

    render = FormulaRender(
        formula_id=formula_id,
        plain_text=plain_text,
        latex=latex or None,
        mathml=mathml or None,
        status=status,
        source="asset",
        source_asset_id=asset_id or None,
        warnings=warnings,
    ).model_dump(mode="json")
    return render, warnings


def formula_renders_from_assets(assets: Iterable[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    renders: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, asset in enumerate(assets, start=1):
        render, render_warnings = formula_render_from_asset(asset, index=index)
        if render is not None:
            renders.append(render)
        warnings.extend(render_warnings)
    return renders, warnings


def _normalize_formula_render(value: Mapping[str, Any], *, index: int = 1) -> tuple[dict[str, Any] | None, list[str]]:
    formula_id = _clean_text(value.get("formula_id")) or f"formula_{index}"
    latex = _clean_text(value.get("latex"))
    mathml = _clean_text(value.get("mathml"))
    plain_text = _first_text(value.get("plain_text"), latex, mathml)
    if not plain_text:
        return None, [f"formula render {formula_id} omitted: no plain-text fallback is available."]

    warnings = [*_latex_warnings(latex), *_mathml_warnings(mathml)]
    status = value.get("status") if value.get("status") in {"renderable", "plain_text_fallback", "invalid_markup"} else None
    if warnings:
        status = "invalid_markup"
        latex = None
        mathml = None
    elif status is None:
        status = "renderable" if latex or mathml else "plain_text_fallback"

    existing_warnings = value.get("warnings")
    try:
        render = FormulaRender(
            schema_version=value.get("schema_version") or "p4.formula_render.v1",
            formula_id=formula_id,
            plain_text=plain_text,
            latex=latex or None,
            mathml=mathml or None,
            status=status,
            source=value.get("source") if value.get("source") in {"asset", "structured_field", "unknown"} else "structured_field",
            source_asset_id=_clean_text(value.get("source_asset_id")) or None,
            warnings=[*(existing_warnings if isinstance(existing_warnings, list) else []), *warnings],
        ).model_dump(mode="json")
    except ValidationError as exc:
        return None, [f"formula render {formula_id} omitted: {exc}"]
    return render, warnings


def normalize_formula_renders(
    raw_renders: Any,
    assets: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    renders: list[dict[str, Any]] = []
    warnings: list[str] = []
    seen: set[str] = set()

    if isinstance(raw_renders, list):
        for index, value in enumerate(raw_renders, start=1):
            if not isinstance(value, Mapping):
                warnings.append(f"formula render {index} omitted: expected object.")
                continue
            render, render_warnings = _normalize_formula_render(value, index=index)
            if render is not None:
                renders.append(render)
                seen.add(str(render["formula_id"]))
            warnings.extend(render_warnings)

    asset_renders, asset_warnings = formula_renders_from_assets(assets)
    for render in asset_renders:
        if str(render["formula_id"]) not in seen:
            renders.append(render)
            seen.add(str(render["formula_id"]))
    warnings.extend(asset_warnings)
    return renders, warnings
