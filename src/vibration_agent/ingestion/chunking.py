"""Semantic chunking with page/section anchors preserved for citations."""
from __future__ import annotations


def chunk_sections(sections: list[dict], *, target_tokens: int = 600) -> list[dict]:
    """Input: structured sections. Output: chunk rows ready for `chunks` table."""
    # TODO: split by headings → sliding window → carry page_start/page_end anchors
    raise NotImplementedError
