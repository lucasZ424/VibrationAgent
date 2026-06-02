"""Unit tests for section parent-child linking (Phase-2 Obj3).

These pin the ancestor-chain contract that feeds the chunk metadata
``section_parent_keys`` field: nesting builds a full root->parent chain, siblings
pop deeper ancestors, and level-0 (front matter) content is parentless and never
anchors descendants.
"""
from vibration_agent.ingestion.section_hierarchy import build_hierarchy_warnings, build_parent_map, section_sequence


def test_nested_sections_build_full_ancestor_chain():
    # A subsection must expose its chapter AND section ancestors so a chunk can
    # be cited / contextualised within the full hierarchy.
    parents = build_parent_map([("s0001", 1), ("s0002", 2), ("s0003", 3)])

    assert parents == {
        "s0001": [],
        "s0002": ["s0001"],
        "s0003": ["s0001", "s0002"],
    }


def test_returning_to_shallower_level_drops_deeper_ancestor():
    # After a level-3 subsection, a new level-2 section is a sibling of the prior
    # level-2 one; it must inherit only the chapter, not the stale subsection.
    parents = build_parent_map([("s0001", 1), ("s0002", 2), ("s0003", 3), ("s0004", 2)])

    assert parents["s0004"] == ["s0001"]


def test_front_matter_level_zero_is_parentless_and_anchors_nothing():
    # Heading-less / front-matter content (level 0) is unsectioned: it carries no
    # parents and must not become an ancestor of the chapters that follow it.
    parents = build_parent_map([("front_matter", 0), ("s0001", 1), ("s0002", 2)])

    assert parents["front_matter"] == []
    assert parents["s0001"] == []
    assert parents["s0002"] == ["s0001"]


def test_section_sequence_dedupes_keeping_first_seen_level():
    # The same section_key recurs across pages; collapsing to first-seen keeps the
    # hierarchy stable instead of re-opening a section at a later page.
    sequence = section_sequence([("s0001", 1), ("s0001", 1), ("s0002", 2), ("s0001", 1)])

    assert sequence == [("s0001", 1), ("s0002", 2)]


def test_empty_input_yields_empty_map():
    assert build_parent_map([]) == {}


def test_level_gap_gets_non_blocking_warning():
    warnings = build_hierarchy_warnings([("s0001", 1), ("s0002", 3)])

    assert warnings["s0001"] == []
    assert warnings["s0002"] == ["section_level_gap"]
