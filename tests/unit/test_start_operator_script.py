import sys

from scripts import start_operator


def test_operator_url_points_to_operator_route():
    assert start_operator._url("127.0.0.1", 8000) == "http://127.0.0.1:8000/operator"
    assert start_operator._url("127.0.0.1", 8000, "/health") == "http://127.0.0.1:8000/health"


def test_server_command_uses_current_python_and_api_app():
    # WHY: the launcher must start the same virtualenv Python that invoked it,
    # otherwise local dependencies and .env loading drift from normal CLI usage.
    command = start_operator._server_command("127.0.0.1", 8000)

    assert command[:4] == [sys.executable, "-m", "uvicorn", "apps.api.main:app"]
    assert command[-2:] == ["--port", "8000"]


def test_server_command_can_enable_uvicorn_reload_for_development():
    command = start_operator._server_command("127.0.0.1", 8000, reload=True)

    assert "--reload" in command


def test_parse_windows_netstat_pid_finds_listening_operator_port():
    # WHY: --stop must target the process actually bound to the operator port,
    # otherwise a stale server can hide new backend changes from the UI.
    output = """
  TCP    127.0.0.1:8000         0.0.0.0:0              LISTENING       4321
  TCP    127.0.0.1:9000         0.0.0.0:0              LISTENING       9999
"""

    assert start_operator._parse_windows_netstat_pid(output, "127.0.0.1", 8000) == 4321
