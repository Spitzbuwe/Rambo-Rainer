from __future__ import annotations

import main as m


def test_direct_run_chat_contains_run_trace_contract():
    with m.app.test_client() as c:
        r = c.post("/api/direct-run", json={"task": "hallo", "scope": "local", "mode": "apply"})
    assert r.status_code == 200
    body = r.get_json() or {}
    rt = body.get("run_trace") or {}
    assert isinstance(rt, dict)
    assert isinstance(rt.get("route"), str) and rt.get("route")
    assert isinstance(rt.get("classification"), str) and rt.get("classification")
    assert isinstance(rt.get("duration_ms"), int) and rt.get("duration_ms") >= 0
    assert isinstance(rt.get("decisions"), list)
