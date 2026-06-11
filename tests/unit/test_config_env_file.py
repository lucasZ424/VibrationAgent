from __future__ import annotations

import os
import shutil
from pathlib import Path

from vibration_agent.config import load


def _workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    shutil.copytree(Path.cwd() / "configs", root / "configs")
    shutil.copytree(Path.cwd() / "src" / "vibration_agent", root / "src" / "vibration_agent")
    return root


def test_load_reads_gitignored_env_local_without_overriding_process_env(tmp_path, monkeypatch):
    # WHY: Manual live validation should not require retyping API keys every
    # shell session, while explicit process env still wins for operator control.
    root = _workspace(tmp_path)
    (root / ".env.local").write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=local-openai-key",
                "ANTHROPIC_API_KEY='local-anthropic-key'",
                "LLM_LIVE_ENABLED=true",
                "LLM_CAPTURE_ENABLED=true # inline comment",
                "OPENAI_MODEL=should-not-win",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_LIVE_ENABLED", raising=False)
    monkeypatch.delenv("LLM_CAPTURE_ENABLED", raising=False)
    monkeypatch.delenv("VIBRATION_AGENT_DISABLE_DOTENV", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "process-model")

    try:
        settings = load(root).llm

        assert os.getenv("OPENAI_API_KEY") == "local-openai-key"
        assert os.getenv("ANTHROPIC_API_KEY") == "local-anthropic-key"
        assert settings.live_enabled is True
        assert settings.capture_enabled is True
        assert settings.openai.model == "process-model"
    finally:
        for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_LIVE_ENABLED", "LLM_CAPTURE_ENABLED"):
            os.environ.pop(name, None)


def test_local_env_loading_can_be_disabled(tmp_path, monkeypatch):
    root = _workspace(tmp_path)
    (root / ".env.local").write_text("LLM_LIVE_ENABLED=true\n", encoding="utf-8")
    monkeypatch.delenv("LLM_LIVE_ENABLED", raising=False)
    monkeypatch.setenv("VIBRATION_AGENT_DISABLE_DOTENV", "1")

    assert load(root).llm.live_enabled is False
