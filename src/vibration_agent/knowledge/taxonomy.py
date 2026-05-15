"""Load taxonomy yaml files at startup and expose lookup helpers.

Tables: glossary, symbols, units, engineering_context. Files live in ../../../taxonomy.
"""
from __future__ import annotations

from pathlib import Path


def load_all(taxonomy_dir: Path) -> dict:
    """Return {glossary, symbols, units, engineering_context}."""
    # TODO: yaml.safe_load each file; validate against a lightweight schema
    raise NotImplementedError
