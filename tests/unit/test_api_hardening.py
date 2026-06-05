from pathlib import Path

from fastapi.testclient import TestClient

import apps.api.main as api_main
from vibration_agent.config import ApiSettings, DatabaseSettings, load


def _settings(*, api: ApiSettings | None = None, database: DatabaseSettings | None = None):
    workspace = Path.cwd()
    settings = load(workspace)
    updates = {}
    if api is not None:
        updates["api"] = api
    if database is not None:
        updates["database"] = database
    return settings.model_copy(update=updates)


def test_api_auth_rejects_missing_token(monkeypatch):
    settings = _settings(api=ApiSettings(auth_enabled=True, api_key="secret"))
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)

    response = TestClient(api_main.app).get("/scope")

    assert response.status_code == 401
    assert response.json()["detail"][0]["loc"] == ["headers", "x-api-key"]


def test_api_auth_rejects_wrong_token(monkeypatch):
    settings = _settings(api=ApiSettings(auth_enabled=True, api_key="secret"))
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)

    response = TestClient(api_main.app).get("/scope", headers={"x-api-key": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"][0]["reason"] == "Missing or invalid API token."


def test_api_auth_accepts_header_token(monkeypatch):
    settings = _settings(api=ApiSettings(auth_enabled=True, api_key="secret"))
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)

    response = TestClient(api_main.app).get("/scope", headers={"x-api-key": "secret"})

    assert response.status_code == 200
    assert "s2_retrieval" in response.json()["active_skills"]


def test_api_ingest_path_whitelist_runs_before_auth(monkeypatch):
    settings = _settings(api=ApiSettings(auth_enabled=True, api_key="secret"))
    outside = settings.paths.workspace.parent

    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)
    response = TestClient(api_main.app).post("/ingest", json={"path": str(outside), "plan_only": True})

    assert response.status_code == 403
    payload = response.json()
    assert payload["detail"][0]["loc"] == ["body", "path"]
    assert "outside the configured workspace" in payload["detail"][0]["reason"]


def test_api_health_reports_degraded_dependency(monkeypatch):
    settings = _settings(
        database=DatabaseSettings(postgres_enabled=True, postgres_url="", qdrant_enabled=False),
    )
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)

    response = TestClient(api_main.app).get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["postgres"]["status"] == "fail"
    assert payload["dependencies"]["qdrant"]["status"] == "disabled"


def test_api_health_status_can_fail_when_all_dependencies_fail():
    assert api_main._health_status(
        {
            "postgres": {"status": "fail", "detail": "down"},
            "qdrant": {"status": "fail", "detail": "down"},
        }
    ) == "fail"


def test_api_rate_limit_rejects_second_request_when_enabled(monkeypatch):
    settings = _settings(api=ApiSettings(rate_limit_enabled=True, rate_limit_per_minute=1))
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)
    api_main.rate_limiter.clear()
    local_client = TestClient(api_main.app)

    first = local_client.get("/scope")
    second = local_client.get("/scope")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["detail"][0]["loc"] == ["headers", "x-rate-limit"]
