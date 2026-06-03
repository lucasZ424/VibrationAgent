import json
import uuid
from pathlib import Path

import pytest

from vibration_agent.config import load
from vibration_agent.schemas import Citation, SkillOutput
from vibration_agent.storage import postgres_client, qa_logs

pytestmark = pytest.mark.integration

_MIGRATIONS = Path(__file__).resolve().parents[2] / "db" / "postgres" / "migrations"


def test_postgres_qa_log_roundtrip_and_idempotent_migrations():
    pytest.importorskip("psycopg")
    settings = load()
    url = settings.database.postgres_url or "postgresql://postgres:postgres@localhost:5432/postgres"
    try:
        conn = postgres_client.connect(url, connect_timeout=2.0)
    except Exception as exc:  # noqa: BLE001 - no live Postgres in this environment
        pytest.skip(f"Postgres instance not available: {exc}")

    try:
        try:
            postgres_client.apply_migrations(conn, _MIGRATIONS)
        except Exception as exc:  # noqa: BLE001 - missing extensions / perms
            pytest.skip(f"Postgres migrations could not be applied: {exc}")

        # AC1: replayable — a second run applies nothing and does not raise.
        assert postgres_client.apply_migrations(conn, _MIGRATIONS) == []

        settings.database.postgres_enabled = True
        settings.database.postgres_url = url
        output = SkillOutput(
            status="ok",
            summary="Damping reduces resonant vibration.",
            citations=[Citation(chunk_id="c1", doc_id="d1", pages=[1], evidence_type="documented", confidence=0.8)],
            structured_result={
                "chain": [{"skill": "s2_retrieval"}, {"skill": "s3_qa_summary"}, {"skill": "v4_style"}],
                "skill_results": {"s2": {"intent": "engineering"}},
            },
        )
        marker = f"rt-{uuid.uuid4().hex}"

        assert qa_logs.record_qa_log(output, query=marker, latency_ms=7, settings=settings) is None

        rows = postgres_client.fetch_rows(conn, "qa_logs", limit=20)
        written = next(row for row in rows if row["query"] == marker)
        assert written["status"] == "ok"
        assert written["latency_ms"] == 7
        # AC4: citations are locatable refs only — no raw chunk text persisted.
        assert "text" not in json.dumps(written["citations"])
        assert written["citations"][0]["chunk_id"] == "c1"
    finally:
        conn.close()
