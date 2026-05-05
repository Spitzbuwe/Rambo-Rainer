# -*- coding: utf-8 -*-
"""Gemeinsame Fixtures: Backend-Prozess, Basis-URL, Admin-Header, frisches state.json."""

from __future__ import annotations

import json
import os
import sys
import socket
import subprocess
import time
from pathlib import Path

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
BACKEND_SCRIPT = PROJECT_ROOT / "backend" / "server.py"
STATE_PATH = PROJECT_ROOT / "data" / "state.json"
FIXTURE_STATE = Path(__file__).resolve().parent / "fixtures" / "minimal_state.json"


def _admin_token_for_requests() -> str:
    env_path = PROJECT_ROOT / ".env"
    if env_path.is_file():
        try:
            from dotenv import dotenv_values

            raw = dotenv_values(str(env_path)).get("RAMBO_ADMIN_TOKEN")
            if raw not in (None, ""):
                return str(raw).strip()
        except Exception:
            pass
    return (
        os.environ.get("RAMBO_ADMIN_TOKEN", "Matze-Mueller-2026-Safe").strip()
        or "Matze-Mueller-2026-Safe"
    )


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_http_ready(base_url: str, timeout_s: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_s
    last_exc = None
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/api/health", timeout=0.5)
            if r.status_code == 200:
                return
        except (requests.RequestException, OSError) as exc:
            last_exc = exc
        time.sleep(0.05)
    raise RuntimeError(f"Backend nicht bereit unter {base_url}: {last_exc!r}")


def _atomic_write_state(obj: dict) -> None:
    PROJECT_ROOT.joinpath("data").mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".json.tmp_pytest")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def _load_fixture_state() -> dict:
    return json.loads(FIXTURE_STATE.read_text(encoding="utf-8"))


@pytest.fixture(scope="function")
def admin_headers():
    return {"X-Rambo-Admin": _admin_token_for_requests()}


@pytest.fixture(scope="function")
def backend_process():
    """Startet Backend pro Test, wartet auf Health, beendet danach.

    Manuell (Port 5035): PYTEST_USE_EXTERNAL_BACKEND=1 setzen — kein Subprozess.
    """
    use_external = os.environ.get("PYTEST_USE_EXTERNAL_BACKEND", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if use_external:
        base_url = os.environ.get("PYTEST_BASE_URL", "http://127.0.0.1:5035").rstrip("/")
        _wait_http_ready(base_url)
        info = {"proc": None, "base_url": base_url, "external": True}
        yield info
        return

    if not BACKEND_SCRIPT.is_file():
        pytest.skip(f"backend fehlt: {BACKEND_SCRIPT}")

    port = int(os.environ.get("PYTEST_BACKEND_PORT", "0") or 0) or _free_port()
    env = os.environ.copy()
    env["BACKEND_PORT"] = str(port)
    env.setdefault("RAMBO_REQUIRE_ADMIN", "true")

    popen_kwargs = {
        "cwd": str(PROJECT_ROOT),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.PIPE,
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    proc = subprocess.Popen([sys.executable, str(BACKEND_SCRIPT)], **popen_kwargs)
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_http_ready(base_url)
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        err = b""
        if proc.stderr:
            err = proc.stderr.read()[:4000]
        pytest.fail(f"Backend-Start fehlgeschlagen: {err.decode(errors='replace')}")

    try:
        yield {"proc": proc, "base_url": base_url, "external": False}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="function")
def base_url(backend_process):
    return backend_process["base_url"]


@pytest.fixture(scope="function")
def fresh_state(backend_process):
    """Vor dem Test: minimale Fixture-State schreiben; danach vorherigen Inhalt wiederherstellen."""
    backup = None
    if STATE_PATH.is_file():
        try:
            backup = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            backup = None
    if FIXTURE_STATE.is_file():
        _atomic_write_state(_load_fixture_state())
    yield
    if backup is not None:
        _atomic_write_state(backup)
    elif STATE_PATH.is_file():
        try:
            STATE_PATH.unlink()
        except OSError:
            pass
