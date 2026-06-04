"""Unit tests for Phase-2 Obj7 qa_logs persistence.

These pin the contract the spec requires: one fail-safe row per handle_query that
stores only locatable citation refs (never raw chunk text or secrets), is a silent
no-op when Postgres is disabled, and turns any write failure into a warning instead
of changing the orchestrator's return status.
"""
import json

import pytest

from vibration_agent.config import load
from vibration_agent.orchestrator.tutor import TutorOrchestrator
from vibration_agent.schemas import Citation, SkillOutput
from vibration_agent.storage import postgres_client, qa_logs
from vibration_agent.storage.postgres import POSTGRES_TABLES, PostgresWritePlan


def _output() -> SkillOutput:
    return SkillOutput(
        status="ok",
        summary="Damping reduces resonant vibration near critical speed.",
        citations=[Citation(chunk_id="c1", doc_id="d1", pages=[1, 2], evidence_type="documented", confidence=0.9)],
        structured_result={
            "chain": [
                {"skill": "s2_retrieval"},
                {"skill": "s3_qa_summary"},
                {"skill": "v2_citation_check"},
                {"skill": "v4_style"},
            ],
            "skill_results": {"s2": {"intent": "engineering"}},
        },
    )


def test_build_qa_log_row_persists_only_locatable_refs():
    # WHY: AC4 — qa_logs must keep locatable references + summaries, never raw
    # chunk text. A citation ref is ids + pages + evidence type only.
    row = qa_logs.build_qa_log_row(_output(), query="rotor damping?", latency_ms=12)

    assert row["citations"] == [
        {"chunk_id": "c1", "doc_id": "d1", "pages": [1, 2], "evidence_type": "documented", "confidence": 0.9}
    ]
    assert row["status"] == "ok"
    assert row["intent"] == "engineering"
    assert row["chosen_skills"] == ["s2_retrieval", "s3_qa_summary", "v2_citation_check", "v4_style"]
    assert row["latency_ms"] == 12
    assert "_meta" not in row  # SQL-ready, no planning helper


def test_build_qa_log_row_is_aligned_with_real_qa_logs_columns():
    # WHY: AC1 — rows must match the migrated qa_logs schema; sql_rows() raises on
    # any unknown column, catching schema drift before a runtime writer hits the DB.
    row = qa_logs.build_qa_log_row(_output(), query="q", latency_ms=1)
    rows = {table: [] for table in POSTGRES_TABLES}
    rows["qa_logs"] = [row]

    sql_rows = PostgresWritePlan(rows=rows).sql_rows()

    assert set(sql_rows["qa_logs"][0]) == set(row)


def test_build_qa_log_row_truncates_overlong_query():
    # WHY: AC4 — never persist long raw text. A pathological query is capped.
    row = qa_logs.build_qa_log_row(_output(), query="x" * 5000, latency_ms=1)

    assert len(row["query"]) <= 2000


def test_record_qa_log_is_silent_noop_when_postgres_disabled(monkeypatch):
    # WHY: AC3 — offline/disabled is the default; no connection is attempted and no
    # warning is produced, so existing answers are byte-identical.
    settings = load()
    settings.database.postgres_enabled = False
    attempts: list[int] = []
    monkeypatch.setattr(postgres_client, "connect", lambda *a, **k: attempts.append(1))

    assert qa_logs.record_qa_log(_output(), query="q", latency_ms=1, settings=settings) is None
    assert attempts == []


def test_record_qa_log_write_failure_returns_warning_and_never_raises(monkeypatch):
    # WHY: AC3 — a write failure must degrade to a warning, never propagate.
    settings = load()
    settings.database.postgres_enabled = True
    settings.database.postgres_url = "postgresql://unused"

    def boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(postgres_client, "connect", boom)

    warning = qa_logs.record_qa_log(_output(), query="q", latency_ms=1, settings=settings)

    assert warning is not None
    assert "qa_logs persistence skipped" in warning


def test_record_qa_log_success_inserts_redacted_row_and_closes_connection(monkeypatch):
    settings = load()
    settings.database.postgres_enabled = True
    settings.database.postgres_url = "postgresql://unused"
    captured: dict = {}

    class FakeConn:
        def close(self) -> None:
            captured["closed"] = True

    def fake_insert(conn, table, row, *, jsonb_columns=()):
        captured["table"] = table
        captured["row"] = row
        captured["jsonb"] = jsonb_columns
        return 1

    monkeypatch.setattr(postgres_client, "connect", lambda url, **k: FakeConn())
    monkeypatch.setattr(postgres_client, "insert_row", fake_insert)

    assert qa_logs.record_qa_log(_output(), query="rotor?", latency_ms=5, settings=settings) is None
    assert captured["table"] == "qa_logs"
    assert captured["jsonb"] == ("citations",)
    assert captured["row"]["status"] == "ok"
    assert captured["closed"] is True


def test_insert_row_builds_parameterized_sql_with_jsonb_cast():
    # WHY: jsonb columns must be json-serialized + cast so the adapter needs no
    # psycopg-specific type imports; everything else is a plain placeholder.
    class FakeCursor:
        executed: tuple | None = None

        def execute(self, sql, params=None):
            self.executed = (sql, params)

        def fetchone(self):
            return (7,)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeConn:
        def __init__(self) -> None:
            self.cur = FakeCursor()
            self.committed = False

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed = True

    conn = FakeConn()
    new_id = postgres_client.insert_row(
        conn, "qa_logs", {"query": "q", "citations": [{"chunk_id": "c1"}]}, jsonb_columns=("citations",)
    )
    sql, params = conn.cur.executed

    assert new_id == 7
    assert sql.startswith("INSERT INTO qa_logs (query, citations)")
    assert "%s::jsonb" in sql
    assert conn.committed is True
    assert json.loads(params[1]) == [{"chunk_id": "c1"}]


def _fake_migration_conn(ledger: set[str], *, base_exists: bool):
    class FakeCursor:
        def __init__(self) -> None:
            self._next_one: tuple = (None,)
            self._rows: list[tuple] = []

        def execute(self, sql, params=None):
            if sql.startswith("SELECT filename"):
                self._rows = [(name,) for name in ledger]
            elif sql.startswith("SELECT to_regclass"):
                self._next_one = ("qa_logs",) if base_exists else (None,)
            elif sql.startswith("INSERT INTO schema_migrations"):
                ledger.add(params[0])

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._next_one

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class FakeConn:
        def cursor(self):
            return FakeCursor()

        def commit(self):
            pass

    return FakeConn()


def test_apply_migrations_is_idempotent_across_runs(tmp_path):
    # WHY: AC1 — migrations must be replayable. A schema_migrations ledger means a
    # second run applies nothing and never re-executes DDL.
    (tmp_path / "001_a.sql").write_text("CREATE TABLE t (id INT);", encoding="utf-8")
    (tmp_path / "002_b.sql").write_text("ALTER TABLE t ADD COLUMN x INT;", encoding="utf-8")
    ledger: set[str] = set()

    first = postgres_client.apply_migrations(_fake_migration_conn(ledger, base_exists=False), tmp_path)
    second = postgres_client.apply_migrations(_fake_migration_conn(ledger, base_exists=False), tmp_path)

    assert first == ["001_a.sql", "002_b.sql"]
    assert second == []


def test_apply_migrations_backfills_preexisting_base_schema(tmp_path):
    # WHY: issue #2 — a DB whose 001 schema was applied out-of-band has an empty
    # ledger; the runner must backfill 001 and apply only 002+, not re-run 001.
    (tmp_path / "001_init.sql").write_text("CREATE TABLE qa_logs (id INT);", encoding="utf-8")
    (tmp_path / "002_qa.sql").write_text("ALTER TABLE qa_logs ADD COLUMN x INT;", encoding="utf-8")
    ledger: set[str] = set()

    applied = postgres_client.apply_migrations(_fake_migration_conn(ledger, base_exists=True), tmp_path)

    assert applied == ["002_qa.sql"]
    assert "001_init.sql" in ledger


def test_handle_query_records_exactly_one_qa_log_side_effect(monkeypatch):
    # WHY: spec — every handle_query persists one row; logging must not change the
    # primary status, and latency is measured over the chain.
    calls: list[tuple] = []
    monkeypatch.setattr(
        qa_logs,
        "record_qa_log",
        lambda output, **kwargs: calls.append((output.status, kwargs["query"], kwargs.get("latency_ms"))),
    )

    out = TutorOrchestrator().handle_query("what is the capital of France?")  # out of scope

    assert out.status == "insufficient"
    assert len(calls) == 1
    assert calls[0][1] == "what is the capital of France?"
    assert isinstance(calls[0][2], int)


def test_handle_query_appends_write_failure_warning(monkeypatch):
    monkeypatch.setattr(
        qa_logs, "record_qa_log", lambda output, **kwargs: "qa_logs persistence skipped (write failed): X"
    )

    out = TutorOrchestrator().handle_query(
        "rotor unbalance critical speed", context={"chunks": []}, constraints={"scope": "in_scope"}
    )

    assert any("qa_logs persistence skipped" in warning for warning in out.warnings)


def test_handle_query_surfaces_unexpected_logging_failure_as_warning(monkeypatch):
    # WHY: issue #3 — fail-safe must not be silent. An unexpected logging bug is
    # surfaced as a warning while the primary status is unchanged.
    def boom(*args, **kwargs):
        raise RuntimeError("logging bug")

    monkeypatch.setattr(qa_logs, "record_qa_log", boom)

    out = TutorOrchestrator().handle_query("damping ratio critical speed")

    assert out.status in {"ok", "insufficient", "fail"}
    assert any("unexpected failure" in warning for warning in out.warnings)


def test_build_qa_log_row_redacts_common_secret_patterns():
    # WHY: issue #5 / AC4 — common credential shapes in free-text fields are masked.
    row = qa_logs.build_qa_log_row(
        _output(), query="use sk-ABCDEFGHIJKLMNOP1234 and api_key=topsecret please", latency_ms=1
    )

    assert "sk-ABCDEFGHIJKLMNOP1234" not in row["query"]
    assert "topsecret" not in row["query"]
    assert "[REDACTED]" in row["query"]


def test_insert_row_rejects_unsafe_identifier():
    # WHY: issue #6 — interpolated SQL identifiers must be validated.
    class _Conn:
        def cursor(self):
            raise AssertionError("must reject identifier before touching the cursor")

        def commit(self):
            ...

    with pytest.raises(ValueError):
        postgres_client.insert_row(_Conn(), "qa_logs; DROP TABLE qa_logs", {"query": "q"})


def test_record_qa_log_uses_configured_connect_timeout(monkeypatch):
    # WHY: issue #4 — a bad host should not pay the 5s psycopg default per query.
    settings = load()
    settings.database.postgres_enabled = True
    settings.database.postgres_url = "postgresql://unused"
    settings.database.postgres_timeout = 1.5
    seen: dict = {}

    class FakeConn:
        def close(self):
            ...

    def fake_connect(url, *, connect_timeout=5.0):
        seen["timeout"] = connect_timeout
        return FakeConn()

    monkeypatch.setattr(postgres_client, "connect", fake_connect)
    monkeypatch.setattr(postgres_client, "insert_row", lambda *a, **k: 1)

    qa_logs.record_qa_log(_output(), query="q", latency_ms=1, settings=settings)

    assert seen["timeout"] == 1.5
