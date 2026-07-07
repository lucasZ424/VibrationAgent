from pathlib import Path

from fastapi.testclient import TestClient

import apps.api.main as api_main
from vibration_agent.config import ApiSettings, DatabaseSettings, EmbeddingSettings, load


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


def test_api_health_does_not_probe_external_dependencies(monkeypatch):
    settings = _settings(
        database=DatabaseSettings(postgres_enabled=True, postgres_url="postgresql://example", qdrant_enabled=True),
    )
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)
    monkeypatch.setattr(api_main, "_postgres_dependency", lambda settings: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(api_main, "_qdrant_dependency", lambda settings: (_ for _ in ()).throw(AssertionError))

    response = TestClient(api_main.app).get("/health")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["dependencies"]["postgres"]["status"] == "enabled"
    assert payload["dependencies"]["qdrant"]["status"] == "enabled"
    assert payload["dependencies"]["qdrant"]["reachable"] == "not_probed"
    assert payload["diagnostics"]["external_dependency_probe"] == "not_run"
    assert payload["diagnostics"]["retrieval"]["configured_mode"] == settings.retrieval.mode
    assert payload["diagnostics"]["stores"]["qdrant"]["collection"] == settings.database.qdrant_collection


def test_api_diagnostics_can_probe_dependencies_explicitly(monkeypatch):
    settings = _settings(
        database=DatabaseSettings(postgres_enabled=True, postgres_url="", qdrant_enabled=False),
    )
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)

    response = TestClient(api_main.app).get("/diagnostics?probe_dependencies=true")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "degraded"
    assert payload["dependencies"]["postgres"]["status"] == "fail"
    assert payload["dependencies"]["qdrant"]["status"] == "disabled"
    assert payload["diagnostics"]["external_dependency_probe"] == "run"
    assert payload["dependencies"]["postgres"]["configured"] is True
    assert payload["dependencies"]["postgres"]["reachable"] is False


def test_api_diagnostics_redacts_probe_details(monkeypatch):
    settings = _settings(
        database=DatabaseSettings(postgres_enabled=True, postgres_url="postgresql://example", qdrant_enabled=False),
    )
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)
    monkeypatch.setattr(
        api_main,
        "_postgres_dependency",
        lambda settings: {
            "status": "fail",
            "detail": "OPENAI_API_KEY=sk-test failed at C:\\Challenge\\secret\\file.txt",
        },
    )

    response = TestClient(api_main.app).get("/diagnostics?probe_dependencies=true")

    detail = response.json()["dependencies"]["postgres"]["detail"]
    assert "sk-test" not in detail
    assert "C:\\Challenge" not in detail
    assert "[redacted]" in detail
    assert "[local-path]" in detail


def test_api_health_status_can_fail_when_all_dependencies_fail():
    assert api_main._health_status(
        {
            "postgres": {"status": "fail", "detail": "down"},
            "qdrant": {"status": "fail", "detail": "down"},
        }
    ) == "fail"


def test_api_diagnostics_exposes_retrieval_and_embedding_runtime(monkeypatch):
    settings = _settings(
        database=DatabaseSettings(qdrant_enabled=True, qdrant_collection="chunks_obj8"),
    )
    settings.embeddings = EmbeddingSettings(
        enabled=True,
        provider="sentence_transformers",
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_version="v1",
    )
    monkeypatch.setattr(api_main, "get_settings", lambda workspace=None: settings)
    monkeypatch.setattr(
        api_main.hybrid,
        "runtime_lexical_cache_stats",
        lambda: {"entry_count": 1, "chunk_count": 4436, "collections": ["chunks_obj8"]},
    )

    response = TestClient(api_main.app).get("/diagnostics")

    payload = response.json()["diagnostics"]
    assert payload["retrieval"]["runtime_source"] == "runtime_qdrant_independent_lanes"
    assert payload["embedding"]["model"] == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert payload["embedding"]["dimension"] == 384
    assert payload["runtime_caches"]["lexical_payloads"]["chunk_count"] == 4436


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
