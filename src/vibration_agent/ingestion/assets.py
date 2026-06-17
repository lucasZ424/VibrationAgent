"""Asset anchoring helpers shared by ingestion parsers."""
from __future__ import annotations

from typing import Any

ANCHOR_SCHEMA_VERSION = "p4.rich_asset_anchor.v1"


def asset_anchor_metadata(
    *,
    source: str,
    page_no: int,
    page_anchor_type: str,
    block_id: str | None = None,
    rendered_page_no: int | None = None,
    relationship_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return optional metadata for locating a parsed asset without changing core schemas.

    ``page_no`` is the parser's current logical page anchor. ``rendered_page_no``
    is present only when a rendered backend can locate the asset on a rendered
    page without guessing.
    """
    anchor: dict[str, Any] = {
        "schema_version": ANCHOR_SCHEMA_VERSION,
        "source": source,
        "page_no": page_no,
        "page_anchor_type": page_anchor_type,
    }
    if block_id:
        anchor["block_id"] = block_id
    if rendered_page_no is not None:
        anchor["rendered_page_no"] = rendered_page_no
    if relationship_id:
        anchor["relationship_id"] = relationship_id
    if extra:
        anchor.update(extra)
    return {"anchor": anchor}


__all__ = ["ANCHOR_SCHEMA_VERSION", "asset_anchor_metadata"]
