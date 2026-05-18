import pytest

from scripts.ingest_folder import main


def test_ingest_folder_modes_are_mutually_exclusive(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["--src", str(tmp_path), "--parse-pages", "--chunk-documents"])

    assert excinfo.value.code == 2