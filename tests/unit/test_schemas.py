import pytest
"""Smoke test — keeps the I/O contract honest."""
from vibration_agent.schemas import Citation, PageBlock, SkillInput, SkillOutput


def test_skill_input_defaults():
    payload = SkillInput(task_id="t1", user_query="what is damping ratio?")
    assert payload.user_mode == "engineering"


def test_skill_output_roundtrip():
    out = SkillOutput(
        status="ok",
        summary="damping ratio ≈ 0.05",
        citations=[Citation(chunk_id="c1", doc_id="d1")],
    )
    assert out.model_dump()["citations"][0]["evidence_type"] == "documented"


def test_asset_bearing_page_blocks_require_asset_id():
    with pytest.raises(ValueError):
        PageBlock(block_id="p0001_b0001", block_type="figure")



def test_page_block_assignment_and_validated_copy_enforce_asset_id():
    block = PageBlock(block_id="p0001_b0001")

    with pytest.raises(ValueError):
        block.block_type = "figure"

    with pytest.raises(ValueError):
        block.validated_copy(block_type="figure")

    copied = block.validated_copy(block_type="figure", asset_id="asset-1")
    assert copied.block_type == "figure"
    assert copied.asset_id == "asset-1"
