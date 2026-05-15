"""FastAPI HTTP entry for Phase-0 development."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI


def _ensure_local_src_importable() -> None:
    root = Path(__file__).resolve().parents[2]
    src = root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


_ensure_local_src_importable()

from vibration_agent.config import load  # noqa: E402
from vibration_agent.schemas import PHASE0_ACTIVE_SKILLS, PHASE0_DEFERRED_SKILLS  # noqa: E402

settings = load()
app = FastAPI(title="Vibration Agent API")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "default_user_mode": settings.default_user_mode,
        "phase0_pipeline": settings.phase0_pipeline,
    }


@app.get("/scope")
def scope() -> dict[str, Any]:
    return {
        "active_skills": PHASE0_ACTIVE_SKILLS,
        "deferred_skills": PHASE0_DEFERRED_SKILLS,
    }


# Target 17 will add POST /ask and POST /ingest after S1-S3 are implemented.