from __future__ import annotations

import json
from pathlib import Path

from scripts.v2_calibration_eval import load_calibration, run_calibration

ROOT = Path(__file__).resolve().parents[2]


def test_phase4_v2_calibration_set_passes_current_baseline():
    report = run_calibration(load_calibration())

    assert report["schema_version"] == "phase4.v2_calibration.report.v2"
    assert report["fixture_schema_version"] == "phase4.v2_calibration.v2"
    assert report["case_count"] >= 11
    assert report["failed_count"] == 0
    assert report["scorecard"]["pass_rate"] == 1.0
    assert report["confusion"]["expected_supported"] >= 5
    assert report["confusion"]["expected_unsupported"] >= 6
    assert report["confusion"]["false_allow"] >= 2
    assert report["confusion"]["false_block"] >= 1
    assert report["scorecard"]["supported_recall"] < 1.0
    assert report["scorecard"]["unsupported_block_rate"] < 1.0


def test_phase4_retrieval_targets_are_labeled_for_obj2_consumption():
    path = ROOT / "tests" / "fixtures" / "retrieval" / "targets.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == "phase4.retrieval_targets.v1"
    assert data["default_required_top_k"] == [5, 10]
    assert len(data["targets"]) >= 4
    for target in data["targets"]:
        assert target["case_id"]
        assert target["query"]
        assert target["required_top_k"] == [5, 10]
        assert isinstance(target["expected_evidence"], list)
        if target.get("expected_status") == "insufficient":
            assert target["expected_evidence"] == []
        else:
            assert target["expected_evidence"]
            for evidence in target["expected_evidence"]:
                assert evidence["chunk_id"]
                assert evidence["doc_id"]
                assert evidence["pages"]


def test_phase4_retrieval_targets_resolve_to_fixture_chunks():
    targets_path = ROOT / "tests" / "fixtures" / "retrieval" / "targets.json"
    targets = json.loads(targets_path.read_text(encoding="utf-8"))["targets"]
    chunk_ids: set[tuple[str, str]] = set()
    for path in (ROOT / "tests" / "fixtures" / "chunks").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            chunk_ids.add((row["doc_id"], row["chunk_id"]))

    expected = [
        (evidence["doc_id"], evidence["chunk_id"])
        for target in targets
        for evidence in target["expected_evidence"]
    ]

    assert expected
    assert all(item in chunk_ids for item in expected)
