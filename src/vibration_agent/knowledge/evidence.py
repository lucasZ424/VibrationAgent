"""Evidence mapping: bind answer claims → chunk/page/section anchors.

Backs the `citations` table (see Appendix B).
"""
from __future__ import annotations


def attach_citations(answer_text: str, hits: list[dict]) -> list[dict]:
    """Return citation rows: [{chunk_id, evidence_type, confidence}, ...]."""
    # TODO: claim extraction + span alignment against retrieved chunks
    raise NotImplementedError
