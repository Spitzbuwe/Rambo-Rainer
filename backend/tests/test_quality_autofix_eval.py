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


def test_quality_task_graph_endpoint():
    with m.app.test_client() as c:
        r = c.get("/api/quality/task-graph?limit=5")
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert isinstance(body.get("entries"), list)


def test_quality_autofix_run_eval_after_merges_eval_into_task_graph(monkeypatch):
    class _CP:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _CP())

    def _fake_cases(cases):
        return (
            [{"name": "n1", "ok": True, "score": 75, "has_text": True, "has_contract": False, "has_checks": False}],
            1,
            75,
        )

    monkeypatch.setattr(m, "_quality_eval_run_cases", _fake_cases)
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/autofix-run",
            json={"task": "t1", "checks": ["python -c \"print(1)\""], "auto_fix": False, "eval_after": True},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    tg = body.get("task_graph") or {}
    assert tg.get("eval_avg_score") == 75
    assert tg.get("eval_total_cases") == 1
    assert body.get("eval_avg_score") == 75


def test_quality_autofix_eval_quick_uses_single_case(monkeypatch):
    class _CP:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: _CP())
    captured: dict = {}

    def _fake_cases(cases):
        captured["len"] = len(list(cases or []))
        return ([{"name": "x", "ok": True, "score": 50, "has_text": True, "has_contract": False, "has_checks": False}], 1, 50)

    monkeypatch.setattr(m, "_quality_eval_run_cases", _fake_cases)
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/autofix-run",
            json={
                "task": "t2",
                "checks": ["python -c \"print(1)\""],
                "auto_fix": False,
                "eval_after": True,
                "eval_quick": True,
            },
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert captured.get("len") == 1
    tg = body.get("task_graph") or {}
    assert tg.get("eval_quick") is True
    assert body.get("eval_quick") is True


def test_autofix_checks_ok_reflects_final_results(monkeypatch):
    class OK:
        def __init__(self):
            self.returncode = 0
            self.stdout = "ok"
            self.stderr = ""

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: OK())
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/autofix-run",
            json={"task": "t", "checks": ["python -c \"print(1)\""], "auto_fix": False},
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("checks_ok") is True


def test_autofix_skip_eval_when_checks_fail(monkeypatch):
    class F:
        def __init__(self):
            self.returncode = 1
            self.stdout = ""
            self.stderr = "fail"

    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: F())
    called = {"n": 0}

    def _fake_cases(cases):
        called["n"] += 1
        return ([], 0, 0)

    monkeypatch.setattr(m, "_quality_eval_run_cases", _fake_cases)
    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/autofix-run",
            json={
                "task": "t",
                "checks": ["python -c \"print(1)\""],
                "auto_fix": False,
                "eval_after": True,
                "skip_eval_on_check_fail": True,
            },
        )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("eval_skipped") is True
    assert called["n"] == 0
    tg = body.get("task_graph") or {}
    assert tg.get("eval_avg_score") is None


def test_eval_suite_attach_updates_recent_graph_head(monkeypatch):
    ts = m.get_timestamp()
    head = {
        "timestamp": ts,
        "task": "t",
        "checks": ["x"],
        "auto_fix": False,
        "initial_failed_count": 0,
        "final_failed_count": 0,
        "score": 100,
        "fix_rounds": [],
    }
    written = []

    def rjf(path, default=None):
        if path == m.QUALITY_EVAL_HISTORY_FILE:
            return []
        if path == m.QUALITY_TASK_GRAPH_FILE:
            return [dict(head)]
        return default if default is not None else []

    def wjf(path, content):
        written.append((path, content))

    monkeypatch.setattr(m, "read_json_file", rjf)
    monkeypatch.setattr(m, "write_json_file", wjf)
    monkeypatch.setattr(
        m,
        "_quality_eval_run_cases",
        lambda cases: ([{"name": "a", "ok": True, "score": 90, "has_text": True, "has_contract": False, "has_checks": False}], 1, 90),
    )
    with m.app.test_client() as c:
        r = c.post("/api/quality/eval-suite", json={"attach_eval_to_latest_graph": True})
    assert r.status_code == 200
    graph_writes = [w for w in written if w[0] == m.QUALITY_TASK_GRAPH_FILE]
    assert graph_writes
    last_graph = graph_writes[-1][1]
    assert isinstance(last_graph, list)
    assert last_graph[0].get("eval_avg_score") == 90
    assert last_graph[0].get("eval_total_cases") == 1
