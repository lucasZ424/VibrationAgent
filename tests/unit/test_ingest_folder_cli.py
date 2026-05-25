import json

import pytest

from scripts.ingest_folder import main


def _stdout_json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_ingest_folder_modes_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["--src", str(tmp_path), "--parse-pages", "--chunk-documents"])

    assert excinfo.value.code == 2


def test_ingest_folder_plan_mode_delegates_to_canonical_cli(tmp_path, capsys):
    code = main(["--src", str(tmp_path)])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["status"] == "insufficient"
    assert payload["stage"] == "input_classification"
    assert payload["workspace"]

def test_ingest_folder_forwards_workspace_to_canonical_cli(tmp_path, capsys):
    source = tmp_path / "empty"
    workspace = tmp_path / "workspace"
    (workspace / "configs").mkdir(parents=True)
    (workspace / "src" / "vibration_agent").mkdir(parents=True)
    source.mkdir()

    code = main(["--workspace", str(workspace), "--src", str(source)])
    payload = _stdout_json(capsys)

    assert code == 2
    assert payload["workspace"] == str(workspace.resolve())
    assert payload["status"] == "insufficient"
