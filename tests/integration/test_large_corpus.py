from __future__ import annotations

import shutil
import sys
from pathlib import Path
from uuid import uuid4

import pytest

pytest.importorskip("fitz")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.bench_large_corpus import run_benchmark  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
pytestmark = [pytest.mark.integration, pytest.mark.slow, pytest.mark.large_corpus]


def test_large_corpus_benchmark_smoke_uses_fixture_and_requires_citations():
    workspace = ROOT / "data" / "tmp" / f"obj8_large_corpus_{uuid4().hex}"
    output = workspace / "exports" / "large_corpus_baseline.json"
    (workspace / "configs").mkdir(parents=True, exist_ok=True)
    (workspace / "src" / "vibration_agent").mkdir(parents=True, exist_ok=True)
    try:
        baseline = run_benchmark(
            corpus=FIXTURES / "raw" / "small_vibration_native.pdf",
            workspace=workspace,
            output=output,
            questions=[
                {
                    "id": "fixture-critical-speed",
                    "query": "What happens near critical speed in rotor vibration?",
                    "expected_terms": ["critical speed"],
                },
                {
                    "id": "fixture-damping",
                    "query": "How does damping affect rotor vibration near resonance?",
                    "expected_terms": ["damping"],
                },
            ],
            max_pages=1,
            top_k=2,
        )
        assert output.exists()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    assert baseline["s1_status"] == "ok"
    assert baseline["document_count"] == 1
    assert baseline["chunk_count"] >= 1
    assert baseline["question_count"] == 2
    assert baseline["no_citation_questions"] == []
    assert baseline["citation_coverage"] == 1.0
    assert baseline["expected_term_hit_rate"] is not None
    assert baseline["questions"][0]["expected_term_hit"] is True
