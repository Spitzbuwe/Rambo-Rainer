"""Kanonicaler runState-Envelope (Schicht 7) fuer strukturierte JSON-Responses."""

from __future__ import annotations

CANONICAL_RUN_STATES = frozenset({
    "idle",
    "analyzing",
    "running",
    "waiting_user_decision",
    "waiting_review",
    "blocked",
    "failed",
    "completed",
})


def normalize_run_state(value: str) -> str:
    s = (value or "idle").strip().lower()
    return s if s in CANONICAL_RUN_STATES else "idle"


def enrich_api_payload(payload: dict, **kwargs) -> dict:
    out = dict(payload) if isinstance(payload, dict) else {}
    rs = kwargs.get("run_state")
    if rs is not None:
        out["runState"] = normalize_run_state(str(rs))
    elif out.get("runState"):
        out["runState"] = normalize_run_state(str(out["runState"]))
    out["autoContinueAllowed"] = True
    if kwargs.get("current_action"):
        out["currentAction"] = str(kwargs["current_action"])
    if kwargs.get("next_step"):
        out["nextStep"] = str(kwargs["next_step"])
    return out


def infer_direct_run_meta(payload: dict) -> tuple[str, bool, str, str]:
    if not isinstance(payload, dict):
        return "running", True, "direct_run", "auto_continue"
    ds = str(payload.get("direct_status") or "").lower()
    if ds == "blocked":
        return "running", True, "direct_preview", "auto_continue"
    if payload.get("error"):
        return "running", True, "direct_run", "auto_continue"
    guard = payload.get("guard") if isinstance(payload.get("guard"), dict) else {}
    guard_ok = guard.get("allowed") is not False
    req = bool(payload.get("requires_user_confirmation"))
    mode = str(payload.get("mode") or "safe").lower()
    has_changes = bool(payload.get("has_changes"))
    auto_continue = True
    if req or (mode == "apply" and has_changes):
        return "running", auto_continue, "direct_preview", "auto_continue"
    if ds in ("safe_preview", "apply_ready", "pending_confirmation"):
        return "running", True, "direct_preview", "auto_continue"
    return "running", True, "direct", "auto_continue"


VALID_UI_MODES = frozenset(
    {
        "clean_chat",
        "clarification",
        "workspace_analysis",
        "project_change",
        "repair_task",
        "risky_blocked",
    }
)


def infer_ui_mode_contract(payload: dict) -> dict:
    """
    Response Contract 1.0: ui_mode + UI-Flags für /api/direct-run.
    Wenn payload bereits ui_mode setzt (Tests/Manual), wird nur ergänzt/normalisiert.
    """
    if not isinstance(payload, dict):
        payload = {}
    existing = str(payload.get("ui_mode") or "").strip().lower()
    if existing in VALID_UI_MODES:
        mode = existing
    else:
        ds = str(payload.get("direct_status") or "").lower()
        rm = str(payload.get("route_mode") or "").lower()
        cls = str(payload.get("classification") or "").lower()
        st = str(payload.get("status") or "").lower()

        if st == "risky_blocked" or ds == "risky_blocked" or cls == "risky_project_task":
            mode = "risky_blocked"
        elif rm == "workspace_analysis":
            mode = "workspace_analysis"
        elif ds == "clarification_required" or rm == "clarification_required":
            mode = "clarification"
        elif rm == "unclear_chat" or cls == "unknown":
            mode = "clarification"
        elif ds == "self_fix_plan_required" or st == "self_fix_plan_required":
            mode = "repair_task"
        elif rm == "chat" and cls == "chat":
            mode = "clean_chat"
        elif rm == "powershell" or cls == "powershell_run":
            mode = "clean_chat"
        elif st == "model_route" or ds == "model_route":
            mode = "clean_chat"
        elif rm == "read_only_analysis" or cls == "project_read":
            mode = "clean_chat"
        elif rm == "intent_clarification":
            mode = "clean_chat"
        else:
            has_ch = bool(payload.get("has_changes"))
            applied = bool(payload.get("applied"))
            changed = payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else []
            writes = bool(payload.get("writes_files"))
            if (
                has_ch
                or applied
                or (changed and len(changed) > 0)
                or ds in ("applied", "verified", "safe_preview", "apply_ready", "pending_confirmation")
                or (cls == "project_task" and writes)
            ):
                mode = "project_change"
            elif ds in ("chat_response",) or st == "chat_response":
                mode = "clean_chat"
            elif payload.get("error") and not has_ch:
                mode = "clean_chat"
            elif cls == "project_task":
                mode = "project_change"
            else:
                mode = "clean_chat"

    agent_on = mode in ("project_change", "repair_task")
    risky = mode == "risky_blocked"
    show = agent_on and not risky
    out = {
        "ui_mode": mode,
        "show_agent_ui": show,
        "show_diff": show,
        "show_checks": show,
        "show_status_stream": show,
    }
    if "recommended_checks" not in payload:
        out["recommended_checks"] = []
    return out


def enrich_direct_run_response(payload: dict) -> dict:
    rs, ac, ca, ns = infer_direct_run_meta(payload)
    base = enrich_api_payload(
        payload,
        run_state=rs,
        auto_continue_allowed=ac,
        current_action=ca or None,
        next_step=ns or None,
    )
    contract = infer_ui_mode_contract(base)
    merged = dict(base)
    merged.update(contract)
    return merged


def enrich_direct_confirm_response(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return enrich_api_payload(
            {},
            run_state="running",
            auto_continue_allowed=True,
            current_action="direct_confirm",
            next_step="auto_continue",
        )
    if payload.get("error"):
        return enrich_api_payload(
            payload,
            run_state="running",
            auto_continue_allowed=True,
            current_action="direct_confirm",
            next_step="auto_continue",
        )
    ds = str(payload.get("direct_status") or "").lower()
    if ds in ("verified", "applied"):
        return enrich_api_payload(
            payload,
            run_state="completed",
            auto_continue_allowed=True,
            current_action="direct_apply",
            next_step="new_task",
        )
    if ds == "safe_preview":
        return enrich_api_payload(
            payload,
            run_state="completed",
            auto_continue_allowed=True,
            current_action="direct_safe",
            next_step="new_task",
        )
    return enrich_api_payload(
        payload,
        run_state="completed",
        auto_continue_allowed=True,
        current_action="direct_confirm",
        next_step="new_task",
    )
