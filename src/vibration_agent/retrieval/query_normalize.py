"""Query normalization (synonyms, symbols, zh/en alias resolution)."""
from __future__ import annotations


def normalize(query: str) -> dict:
    """Return {normalized_query, detected_terms, detected_symbols, intent_hint}."""
    # TODO: apply taxonomy (glossary, symbols) for term expansion
    raise NotImplementedError
