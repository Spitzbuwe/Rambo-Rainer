from __future__ import annotations

import main as m


def test_quality_autofix_run_without_fix(monkeypatch):
    class _CP:
        def __init__(self, rc: int):
            self.returncode = rc
            self.stdout = "ok" if rc == 0 else ""
            self.stderr = "" if rc == 0 else "fail"

    calls = {"n": 0}

    def _fake_run(*args, **kwargs):
        calls["n"] += 1
        return _CP(0)

    monkeypatch.setattr(m.subprocess, "run", _fake_run)
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/autofix-run",
            json={"task": "prüfe", "checks": ["python -m pytest tests -q"], "auto_fix": False},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["failed_count"] == 0
    assert calls["n"] >= 1


def test_quality_eval_suite_returns_score():
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/eval-suite",
            json={"prompts": [{"name": "chat", "task": "hallo", "scope": "local", "mode": "apply"}]},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert isinstance(body.get("avg_score"), int)
    assert isinstance(body.get("cases"), list)


def test_quality_eval_history_endpoint():
    with m.app.test_client() as c:
        r = c.get("/api/quality/eval-history?limit=5")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert isinstance(body.get("entries"), list)
