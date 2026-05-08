from __future__ import annotations

import main as m


def test_direct_run_risky_block_has_policy_gate():
    with m.app.test_client() as c:
        r = c.post(
            "/api/direct-run",
            json={"task": "Führe git push --force auf main aus bitte", "scope": "local", "mode": "apply"},
        )
    assert r.status_code == 403
    body = r.get_json() or {}
    pg = body.get("policy_gate") or {}
    assert isinstance(pg, dict)
    assert pg.get("allowed") is False
    assert isinstance(pg.get("reason"), str)


def test_write_audit_event_persists_for_blocked_decision():
    event_id = m._append_write_audit_event(
        run_id="r1",
        scope="local",
        mode="apply",
        decision="guard_blocked",
        allowed=False,
        reason="blocked",
        task="x",
        target_files=["frontend/src/App.jsx"],
    )
    assert isinstance(event_id, str) and event_id.startswith("audit_")
    rows = m.read_json_file(m.WRITE_AUDIT_LOG_FILE, [])
    assert isinstance(rows, list) and rows
    head = rows[0]
    assert head.get("event_id") == event_id
    assert head.get("decision") == "guard_blocked"
