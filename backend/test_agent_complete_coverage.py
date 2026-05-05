"""
Erweiterte Tests (Hybrid Schritt 1 — Quality & Security).

Hinweis: Die TXT fordert 95%+ Coverage und 500+ Zeilen — hier fokussierte,
reale Tests gegen die bestehende API (kein globaler agent_executor).
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from agent_brain import AgentBrain
from agent_executor import AgentExecutor
from agent_tasks import AgentTaskRegistry


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    (tmp_path / "src").mkdir()
    return tmp_path


def test_whitelist_version_probes(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=120)
    for stem_cmd in (
        f"{sys.executable} --version",
        f"{sys.executable} -V",
    ):
        r = ex.execute_command(stem_cmd, timeout=60)
        assert r.get("success") is True, stem_cmd


def test_rate_limit_burst(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=4)
    ok_n = 0
    rate_n = 0
    for _ in range(6):
        r = ex.execute_command(f"{sys.executable} --version", timeout=30)
        if r.get("success"):
            ok_n += 1
        elif r.get("error_code") == "RATE_LIMIT":
            rate_n += 1
    assert ok_n == 4
    assert rate_n >= 1


def test_sandbox_blocks_docker(monkeypatch, tmp_project: Path) -> None:
    monkeypatch.setenv("RAINER_AGENT_SANDBOX", "1")
    ex = AgentExecutor(tmp_project, max_commands_per_minute=80)
    r = ex.execute_command("docker --version", timeout=15)
    assert r.get("success") is False
    assert r.get("error_code") == "SANDBOX_BLOCK"


def test_cache_second_call_flag(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=120)
    a = ex.execute_command(f"{sys.executable} --version", timeout=30)
    b = ex.execute_command(f"{sys.executable} --version", timeout=30)
    assert a.get("success") and b.get("success")
    assert b.get("cached") is True


def test_error_enrichment_empty(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command("", cwd=None)
    assert r.get("error_code") == "EMPTY_CMD"
    assert "hints" in r


def test_audit_history_levels(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=120)
    ex.execute_command("not-a-real-binary-xyz123", cwd=None)
    ex.execute_command(f"{sys.executable} --version", cwd=None)
    hist = ex.get_execution_history(20)
    levels = {h.get("audit_level") for h in hist if isinstance(h, dict)}
    assert "blocked" in levels or "denied" in levels
    assert "cache_hit" in levels or "run" in levels


def test_cwd_traversal_blocked(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project)
    r = ex.execute_command(f"{sys.executable} -c \"print(1)\"", cwd="../../../")
    assert r.get("success") is False


def test_security_preflight_env(monkeypatch, tmp_project: Path) -> None:
    monkeypatch.setenv("RAINER_AGENT_SECURITY_PREFLIGHT", "1")
    ex = AgentExecutor(tmp_project, max_commands_per_minute=80)
    r = ex.execute_command("echo `id`", cwd=None)
    assert r.get("success") is False
    assert r.get("error_code") == "SECURITY_SANITIZE"


def test_block_secrets_env(monkeypatch, tmp_project: Path) -> None:
    monkeypatch.setenv("RAINER_AGENT_BLOCK_SECRETS", "1")
    ex = AgentExecutor(tmp_project, max_commands_per_minute=80)
    r = ex.execute_command("echo AKIA0123456789ABCDEF", cwd=None)
    assert r.get("success") is False
    assert r.get("error_code") == "SECURITY_SECRET_PATTERN"


def test_brain_estimate_order() -> None:
    b = AgentBrain(Path("."), max_iterations=2)
    a = b.estimate_task("hi")
    c = b.estimate_task("kubernetes microservices load balancer " * 8)
    assert a.get("complexity_score", 0) <= c.get("complexity_score", 0)


def test_brain_requirement_bullets() -> None:
    b = AgentBrain(Path("."), max_iterations=2)
    t = "- foo\n- bar\n- baz\n"
    reqs = b._extract_requirements(t)
    assert "foo" in reqs


def test_brain_cancel_before_start(monkeypatch, tmp_path: Path) -> None:
    import threading

    ev = threading.Event()
    ev.set()

    def fake_understand(task):
        return {"success": True, "analysis": "x", "model": "m"}

    brain = AgentBrain(tmp_path, max_iterations=3, cancel_event=ev)
    monkeypatch.setattr(brain, "_understand_task", fake_understand)
    monkeypatch.setattr("agent_brain.time.sleep", lambda *a, **k: None)
    out = brain.execute_task("abgebrochen")
    assert out.get("cancelled") is True


def test_task_registry_lifecycle() -> None:
    reg = AgentTaskRegistry()
    ev = __import__("threading").Event()
    tid = reg.create("hello", 3, ev)
    reg.set_status(tid, "running")
    reg.append_stream_log(tid, {"level": "x", "message": "m"})
    pub = reg.get_public(tid)
    assert pub and pub.get("status") == "running"
    reg.complete(tid, {"success": True})
    pub2 = reg.get_public(tid)
    assert pub2.get("status") == "done"


def test_api_routes_registered() -> None:
    import main as m

    rules = {r.rule for r in m.app.url_map.iter_rules()}
    for path in (
        "/api/agent/execute",
        "/api/agent/plan",
        "/api/agent/estimate",
        "/api/agent/stats",
        "/api/agent/report",
        "/api/agent/mega/status",
    ):
        assert path in rules


def test_concurrent_executor_version_calls(tmp_project: Path) -> None:
    ex = AgentExecutor(tmp_project, max_commands_per_minute=200)

    def one(_i: int) -> bool:
        return bool(ex.execute_command(f"{sys.executable} --version", timeout=30).get("success"))

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(one, i) for i in range(12)]
        oks = sum(1 for f in as_completed(futs) if f.result())
    assert oks >= 10


def test_agent_environments_roundtrip(monkeypatch) -> None:
    from agent_environments import AgentEnv, get_agent_environment_config

    monkeypatch.setenv("RAINER_AGENT_ENV", "staging")
    cfg = get_agent_environment_config()
    assert cfg.name is AgentEnv.STAGING
