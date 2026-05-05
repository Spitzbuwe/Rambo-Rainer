"""Tests fuer kanonischen runState-Envelope (Direkt-API)."""

from api_run_state import enrich_direct_confirm_response, enrich_direct_run_response


def test_enrich_direct_run_blocked():
    p = enrich_direct_run_response({"direct_status": "blocked", "guard": {"allowed": False}})
    assert p["runState"] == "running"
    assert p["autoContinueAllowed"] is True
    assert "currentAction" in p


def test_enrich_direct_run_waiting_decision():
    p = enrich_direct_run_response(
        {
            "direct_status": "apply_ready",
            "mode": "apply",
            "has_changes": True,
            "requires_user_confirmation": True,
            "guard": {"allowed": True},
        }
    )
    assert p["runState"] == "running"
    assert p["autoContinueAllowed"] is True


def test_enrich_direct_confirm_completed():
    p = enrich_direct_confirm_response({"direct_status": "verified", "message": "ok"})
    assert p["runState"] == "completed"
    assert p["autoContinueAllowed"] is True


def test_enrich_direct_confirm_error():
    p = enrich_direct_confirm_response({"error": "nope"})
    assert p["runState"] == "running"
    assert p["autoContinueAllowed"] is True
