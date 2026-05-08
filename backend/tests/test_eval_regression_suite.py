from __future__ import annotations

import main as m


def test_eval_suite_default_contract_stable(monkeypatch):
    rows = [
        {"name": "chat_connectivity", "ok": True, "score": 100, "has_text": True, "has_contract": True, "has_checks": True},
        {"name": "read_intent", "ok": True, "score": 85, "has_text": True, "has_contract": True, "has_checks": True},
        {"name": "change_intent", "ok": True, "score": 80, "has_text": True, "has_contract": True, "has_checks": True},
    ]

    monkeypatch.setattr(m, "_quality_eval_run_cases", lambda cases: (list(rows), 3, 88))

    with m.app.test_client() as c:
        r = c.post("/api/quality/eval-suite", json={})

    assert r.status_code == 200
    body = r.get_json() or {}
    assert body.get("ok") is True
    assert body.get("total_cases") == 3
    assert body.get("avg_score") == 88
    out_rows = body.get("cases") or []
    assert isinstance(out_rows, list)
    assert [str(x.get("name")) for x in out_rows] == ["chat_connectivity", "read_intent", "change_intent"]
    for row in out_rows:
        assert isinstance(row.get("ok"), bool)
        assert 0 <= int(row.get("score") or 0) <= 100


def test_eval_suite_custom_prompts_contract_stable(monkeypatch):
    custom_rows = [
        {"name": "case_a", "ok": True, "score": 90, "has_text": True, "has_contract": True, "has_checks": True},
        {"name": "case_b", "ok": False, "score": 35, "has_text": False, "has_contract": True, "has_checks": False},
    ]

    monkeypatch.setattr(m, "_quality_eval_run_cases", lambda cases: (list(custom_rows), 2, 62))

    with m.app.test_client() as c:
        r = c.post(
            "/api/quality/eval-suite",
            json={"prompts": [{"name": "a", "task": "x", "scope": "local", "mode": "apply"}]},
        )

    assert r.status_code == 200
    body = r.get_json() or {}
    assert body.get("ok") is True
    assert body.get("total_cases") == 2
    assert body.get("avg_score") == 62
    out_rows = body.get("cases") or []
    assert len(out_rows) == 2
    assert any(str(x.get("name")) == "case_b" for x in out_rows)


def test_eval_suite_score_bounds_regression(monkeypatch):
    monkeypatch.setattr(
        m,
        "_quality_eval_run_cases",
        lambda cases: ([{"name": "x", "ok": True, "score": 0, "has_text": True, "has_contract": True, "has_checks": True}], 1, 0),
    )
    with m.app.test_client() as c:
        r = c.post("/api/quality/eval-suite", json={})
    assert r.status_code == 200
    body = r.get_json() or {}
    assert 0 <= int(body.get("avg_score") or 0) <= 100
