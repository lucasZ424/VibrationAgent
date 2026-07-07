"""Start the local API and open the operator UI."""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


def _workspace() -> Path:
    return Path(__file__).resolve().parents[1]


def _url(host: str, port: int, path: str = "/operator") -> str:
    return f"http://{host}:{port}{path}"


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def _health_ok(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(_url(host, port, "/health"), timeout=0.75) as response:
            return 200 <= response.status < 300
    except (OSError, urllib.error.URLError):
        return False


def _server_command(host: str, port: int, *, reload: bool = False) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload:
        command.append("--reload")
    return command


def _parse_windows_netstat_pid(output: str, host: str, port: int) -> int | None:
    suffix = f":{port}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid_text = parts[4]
        if state != "LISTENING" or not local_address.endswith(suffix):
            continue
        bound_host = local_address.rsplit(":", 1)[0].strip("[]")
        if bound_host not in {host, "0.0.0.0", "::", "::1", "127.0.0.1"}:
            continue
        try:
            return int(pid_text)
        except ValueError:
            return None
    return None


def _pid_for_port(host: str, port: int) -> int | None:
    if os.name != "nt":
        return None
    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    return _parse_windows_netstat_pid(result.stdout, host, port)


def _stop_pid(pid: int) -> bool:
    if os.name == "nt":
        result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
        return result.returncode == 0
    try:
        os.kill(pid, 15)
        return True
    except OSError:
        return False


def _wait_for_port_closed(host: str, port: int, *, timeout_s: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not _port_open(host, port):
            return True
        time.sleep(0.2)
    return not _port_open(host, port)


def _stop_server(host: str, port: int) -> int:
    if not _port_open(host, port):
        print(f"No server is listening on {host}:{port}.")
        return 0
    if not _health_ok(host, port):
        print(f"Port {port} is in use, but it does not look like the operator API.", file=sys.stderr)
        return 2
    pid = _pid_for_port(host, port)
    if pid is None:
        print(f"Could not identify the process listening on {host}:{port}.", file=sys.stderr)
        return 3
    if not _stop_pid(pid):
        print(f"Failed to stop process {pid}.", file=sys.stderr)
        return 1
    if not _wait_for_port_closed(host, port):
        print(f"Process {pid} was stopped, but port {port} is still open.", file=sys.stderr)
        return 1
    print(f"Stopped operator API process {pid}.")
    return 0


def _wait_for_health(host: str, port: int, *, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _health_ok(host, port):
            return True
        time.sleep(0.2)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the local Vibration Agent operator UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="Start server without opening the browser.")
    parser.add_argument("--stop", action="store_true", help="Stop the operator API listening on the selected port.")
    parser.add_argument("--restart", action="store_true", help="Stop any existing operator API on the port, then start it.")
    parser.add_argument("--reload", action="store_true", help="Start uvicorn with reload enabled for local development.")
    parser.add_argument("--startup-timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    operator_url = _url(args.host, args.port)
    if args.stop:
        return _stop_server(args.host, args.port)

    if args.restart and _port_open(args.host, args.port):
        stop_status = _stop_server(args.host, args.port)
        if stop_status != 0:
            return stop_status

    if _port_open(args.host, args.port):
        if not _health_ok(args.host, args.port):
            print(f"Port {args.port} is already in use but /health is not responding.", file=sys.stderr)
            return 2
        print(f"Using existing API server: {operator_url}")
        if not args.no_browser:
            webbrowser.open(operator_url)
        return 0

    process = subprocess.Popen(_server_command(args.host, args.port, reload=args.reload), cwd=_workspace())
    try:
        if not _wait_for_health(args.host, args.port, timeout_s=args.startup_timeout):
            print(f"API did not become healthy within {args.startup_timeout:.1f}s.", file=sys.stderr)
            process.terminate()
            return 1
        print(f"Operator UI: {operator_url}")
        if not args.no_browser:
            webbrowser.open(operator_url)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
