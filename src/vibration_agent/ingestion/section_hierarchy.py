"""Section parent-child linking for chunk metadata.

Phase-2 Obj3. Given the document's ordered sections (each a ``(section_key,
level)`` pair, where ``level`` is the heading depth produced by the chunker), this
module computes each section's ancestor chain. The result feeds the optional
``section_parent_keys`` chunk-metadata field.

Kept intentionally free of any chunking imports so the dependency stays one-way
(``chunking`` -> ``section_hierarchy``). Callers pass plain tuples.
"""
from __future__ import annotations

from typing import Iterable

# Level 0 / unsectioned content (mirrors chunking.FRONT_MATTER_SECTION_KEY). It
# never participates in the ancestor stack and always maps to no parents.
UNSECTIONED_LEVEL = 0


def section_sequence(items: Iterable[tuple[str, int]]) -> list[tuple[str, int]]:
    """De-duplicate ``(section_key, level)`` pairs, keeping first-seen order/level."""
    seen: set[str] = set()
    sequence: list[tuple[str, int]] = []
    for key, level in items:
        if key not in seen:
            seen.add(key)
            sequence.append((key, level))
    return sequence


def build_parent_map(sections: Iterable[tuple[str, int]]) -> dict[str, list[str]]:
    """Map each section_key to its ancestor keys, ordered root -> immediate parent.

    Stack-based on heading level: a section's parents are the open sections at
    strictly shallower levels. Sections at ``UNSECTIONED_LEVEL`` (front matter,
    heading-less zh content) carry no parents and do not anchor any descendants.
    """
    parents: dict[str, list[str]] = {}
    stack: list[tuple[str, int]] = []
    for key, level in section_sequence(sections):
        if level <= UNSECTIONED_LEVEL:
            parents.setdefault(key, [])
            continue
        while stack and stack[-1][1] >= level:
            stack.pop()
        parents[key] = [ancestor_key for ancestor_key, _ in stack]
        stack.append((key, level))
    return parents


def build_hierarchy_warnings(sections: Iterable[tuple[str, int]]) -> dict[str, list[str]]:
    """Return non-blocking diagnostics for heading-level hierarchy.

    Section parents are inferred from detected heading levels, not from semantic
    document understanding. If a heading level skips an intermediate parent, the
    parent map stays best-effort and the affected section receives a warning.
    """
    warnings: dict[str, list[str]] = {}
    stack: list[tuple[str, int]] = []
    for key, level in section_sequence(sections):
        section_warnings: list[str] = []
        if level <= UNSECTIONED_LEVEL:
            warnings[key] = []
            continue
        expected_parent_level = level - 1
        if expected_parent_level > UNSECTIONED_LEVEL and not any(
            parent_level == expected_parent_level for _, parent_level in stack
        ):
            section_warnings.append("section_level_gap")
        while stack and stack[-1][1] >= level:
            stack.pop()
        warnings[key] = section_warnings
        stack.append((key, level))
    return warnings
