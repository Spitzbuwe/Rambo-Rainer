"""Tests fuer agent_executor (Whitelist, kein shell)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agent_executor import AgentExecutor


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / "sub").mkdir()
    return tmp_path


def test_execute_python_print(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command(
        f'{sys.executable} -c "print(\'hello_agent\')"',
        cwd=None,
        timeout=30,
    )
    assert r.get("success") is True
    assert r.get("returncode") == 0
    assert "hello_agent" in (r.get("stdout") or "") + (r.get("stderr") or "")


def test_block_disallowed_executable(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command("rm -rf x", cwd=None)
    assert r.get("success") is False
    assert "nicht erlaubt" in (r.get("error") or "").lower() or "Programm" in (r.get("error") or "")


def test_block_shell_metacharacters(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command(f"{sys.executable} -c \"print(1)\" && echo bad", cwd=None)
    assert r.get("success") is False


def test_cwd_must_stay_under_root(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command(f"{sys.executable} -c \"print(1)\"", cwd="../../..")
    assert r.get("success") is False


def test_error_envelope_has_code(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command("", cwd=None)
    assert r.get("error_code") == "EMPTY_CMD"


def test_rate_limit(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=2)
    a = ex.execute_command(f"{sys.executable} --version", cwd=None, timeout=30)
    b = ex.execute_command(f"{sys.executable} --version", cwd=None, timeout=30)
    c = ex.execute_command(f"{sys.executable} --version", cwd=None, timeout=30)
    assert a.get("success") is True
    assert b.get("success") is True
    assert c.get("success") is False
    assert c.get("error_code") == "RATE_LIMIT"


def test_parallel_version_probes(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=60)
    cmds = [f"{sys.executable} --version", f"{sys.executable} -V"]
    r = ex.execute_commands_parallel(cmds, cwd=None, timeout=60)
    assert r.get("mode") == "parallel"
    assert r.get("success") is True


def test_sandbox_blocks_docker(monkeypatch, tmp_project: Path) -> None:
    monkeypatch.setenv("RAINER_AGENT_SANDBOX", "1")
    ex = AgentExecutor(tmp_project, max_commands_per_minute=60)
    r = ex.execute_command("docker --version", cwd=None, timeout=10)
    assert r.get("success") is False
    assert r.get("error_code") == "SANDBOX_BLOCK"
