from pathlib import Path


def test_pytest_temp_root_preparation_preserves_other_active_sessions(
    tmp_path, monkeypatch, request
):
    # WHY: starting one pytest process must not delete another process's active basetemp.
    conftest = next(
        plugin
        for plugin in request.config.pluginmanager.get_plugins()
        if Path(getattr(plugin, "__file__", "")).name == "conftest.py"
        and Path(getattr(plugin, "__file__", "")).parent.name == "tests"
    )
    safe_root = tmp_path / "safe"
    active_session = safe_root / "va-pytest-123-active"
    active_session.mkdir(parents=True)
    marker = active_session / "in-use.txt"
    marker.write_text("active", encoding="utf-8")
    monkeypatch.setattr(conftest, "_pytest_tmp_root", lambda: safe_root)

    prepared = conftest._prepare_safe_tmp_root()

    assert prepared == safe_root
    assert marker.read_text(encoding="utf-8") == "active"
