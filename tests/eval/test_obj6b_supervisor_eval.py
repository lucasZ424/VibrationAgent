from scripts.obj6b_supervisor_eval import run_eval


def test_obj6b_supervisor_replay_gate_records_correction_contract(tmp_path):
    # WHY: Obj6B must prove reject->correct->approve through hashed replay
    # fixtures, not by trusting named canned responses or live-only behavior.
    report = run_eval(fixture_dir=tmp_path)

    assert report["passed"] is True
    assert report["supervisor_status"] == "approved"
    assert report["supervisor_invocations"] == 2
    assert report["supervisor_corrections"] == 1
    assert report["supervisor_token_cost"] == 60
    assert report["supervisor_residual_risk"] == "Low residual risk after correction."
    assert set(report["request_hashes"]) == {"review_reject", "correction", "review_approve"}
