"""Shared storage mapping rules.

These mappings keep relational rows and vector payloads on the same vocabulary
without making one storage adapter depend on another adapter's module internals.
"""

CHUNK_TYPE_MAP = {
    "body": "text",
    "section_summary": "text",
    "formula_context": "formula",
    "figure_context": "caption",
    "table_context": "table",
}


def normalize_chunk_type(chunk_type: object) -> str:
    value = str(chunk_type or "body")
    return CHUNK_TYPE_MAP.get(value, value)
