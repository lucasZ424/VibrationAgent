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