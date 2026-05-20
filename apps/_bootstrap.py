"""Shared import bootstrap for app entry points."""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_local_imports(entry_file: str | Path) -> Path:
    """Make the repository root and src layout importable for local runners."""
    root = Path(entry_file).resolve().parents[2]
    src = root / "src"
    for path in (root, src):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    return root