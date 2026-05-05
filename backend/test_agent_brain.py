"""Tests fuer AgentBrain und Agent-API."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from agent_brain import AgentBrain


def test_agent_brain_success_one_iteration(monkeypatch, tmp_path: Path) -> None:
    import sys

    def fake_understand(task):
        return {"success": True, "analysis": "Kurzanalyse", "model": "m"}

    def fake_optimized(*args, **kwargs):
        return {
            "success": True,
            "response": "Plan\nCommand: " + sys.executable + ' -c "print(99)"\n',
            "model": "m",
        }

    brain = AgentBrain(tmp_path, max_iterations=3)
    monkeypatch.setattr("agent_brain.time.sleep", lambda *a, **k: None)
    monkeypatch.setattr(brain, "_understand_task", fake_understand)
    monkeypatch.setattr("agent_brain.hybrid_optimizer.execute_optimized", fake_optimized)
    out = brain.execute_task("nur test")
    assert out.get("success") is True
    assert out.get("iterations") == 1
    assert isinstance(out.get("log"), list)
    assert any(e.get("level") == "SUCCESS" for e in out["log"])


def test_agent_execute_api_smoke(monkeypatch):
    import main as m

    def fake_execute_task(self, task):
        return {
            "success": True,
            "iterations": 1,
            "result": {"all_success": True},
            "history": [],
            "log": [],
        }

    monkeypatch.setattr(AgentBrain, "execute_task", fake_execute_task)
    c = m.app.test_client()
    r = c.post("/api/agent/execute", json={"task": "ping"})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("success") is True


def test_agent_capabilities_route():
    import main as m

    c = m.app.test_client()
    r = c.get("/api/agent/capabilities")
    assert r.status_code == 200
    assert r.get_json().get("ok") is True


def test_rainer_capabilities_overview():
    import main as m

    c = m.app.test_client()
    r = c.get("/api/capabilities")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("rainer_build") == "3.0"
    assert any("Autonom" in x for x in (data.get("features") or []))


def test_agent_history_status_test_routes():
    import main as m

    c = m.app.test_client()
    st = c.get("/api/agent/status")
    assert st.status_code == 200
    assert st.get_json().get("ok") is True
    h0 = c.get("/api/agent/history?limit=3")
    assert h0.status_code == 200
    tr = c.post("/api/agent/test")
    assert tr.status_code == 200
    tb = tr.get_json()
    assert tb.get("ok") is True
    h1 = c.get("/api/agent/history?limit=5")
    assert h1.status_code == 200
    assert (h1.get_json().get("total") or 0) >= 1


def test_agent_estimate_heuristic():
    b = AgentBrain(Path("."), max_iterations=3)
    e = b.estimate_task("Kurz")
    assert e.get("ok") is True
    assert e.get("complexity") in ("low", "medium", "high")


def test_agent_estimate_http():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/agent/estimate", json={"task": "Hello"})
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("ok") is True
    assert j.get("estimate", {}).get("complexity")


def test_agent_plan_stats_report_routes(monkeypatch):
    import main as m

    def fake_plan(self, task):
        return {
            "success": True,
            "parsed_commands": ["echo"],
            "command_count": 1,
            "log": [],
            "plan": {"success": True, "plan": "Command: x"},
            "understanding": {"success": True},
        }

    monkeypatch.setattr(AgentBrain, "plan_task", fake_plan)
    c = m.app.test_client()
    pr = c.post("/api/agent/plan", json={"task": "demo"})
    assert pr.status_code == 200
    assert pr.get_json().get("ok") is True
    st = c.get("/api/agent/stats")
    assert st.status_code == 200
    rp = c.get("/api/agent/report")
    assert rp.status_code == 200


def test_agent_async_execute_logs(monkeypatch):
    import main as m

    def fake_execute_task(self, task):
        return {
            "success": True,
            "iterations": 1,
            "result": {},
            "history": [],
            "log": [{"level": "DONE", "message": "ok", "timestamp": 1.0, "iteration": 1}],
        }

    monkeypatch.setattr(AgentBrain, "execute_task", fake_execute_task)
    c = m.app.test_client()
    r = c.post("/api/agent/execute", json={"task": "async ping", "async": True})
    assert r.status_code == 200
    tid = r.get_json().get("task_id")
    assert tid
    time.sleep(0.25)
    lg = c.get(f"/api/agent/logs/{tid}")
    assert lg.status_code == 200
    body = lg.get_json()
    assert body.get("ok") is True
    assert body.get("task", {}).get("status") in ("done", "running", "pending")


def test_agent_execute_returns_log_key(monkeypatch):
    import main as m

    def fake_execute_task(self, task):
        return {"success": True, "iterations": 1, "result": {}, "history": [], "log": [{"level": "X", "message": "y"}]}

    monkeypatch.setattr(AgentBrain, "execute_task", fake_execute_task)
    c = m.app.test_client()
    r = c.post("/api/agent/execute", json={"task": "ping"})
    assert r.status_code == 200
    body = r.get_json()
    assert isinstance(body.get("log"), list)
    assert len(body["log"]) == 1
