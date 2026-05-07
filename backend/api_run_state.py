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


def _infer_recommended_checks(payload: dict, ui_mode: str) -> list[str]:
    if not isinstance(payload, dict):
        return []
    existing = payload.get("recommended_checks")
    if isinstance(existing, list) and existing:
        return [str(x).strip() for x in existing if str(x).strip()]
    if ui_mode not in {"project_change", "repair_task"}:
        return []
    changed = payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else []
    changed_txt = " ".join(str(x).lower() for x in changed)
    checks: list[str] = ["python -m py_compile backend/main.py"]
    if "frontend/" in changed_txt:
        checks.append("npm run lint")
    checks.append("python -m pytest tests -q")
    seen: set[str] = set()
    out: list[str] = []
    for c in checks:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _infer_confidence(payload: dict, ui_mode: str) -> dict:
    if not isinstance(payload, dict):
        return {"confidence_score": 35, "confidence_label": "low", "confidence_reason": "unstructured_payload"}
    if payload.get("error"):
        return {"confidence_score": 20, "confidence_label": "low", "confidence_reason": "error_present"}
    if ui_mode in {"clean_chat", "clarification", "workspace_analysis"}:
        return {"confidence_score": 70, "confidence_label": "medium", "confidence_reason": "chat_or_read_mode"}
    has_changes = bool(payload.get("has_changes")) or bool(payload.get("applied"))
    verification = payload.get("verification_summary") if isinstance(payload.get("verification_summary"), dict) else {}
    failed = verification.get("failed") if isinstance(verification.get("failed"), list) else []
    blocked = verification.get("blocked") if isinstance(verification.get("blocked"), list) else []
    if failed or blocked:
        return {"confidence_score": 35, "confidence_label": "low", "confidence_reason": "verification_failed_or_blocked"}
    if has_changes and verification:
        return {"confidence_score": 88, "confidence_label": "high", "confidence_reason": "changes_with_verification"}
    if has_changes:
        return {"confidence_score": 62, "confidence_label": "medium", "confidence_reason": "changes_without_verification"}
    return {"confidence_score": 72, "confidence_label": "medium", "confidence_reason": "no_changes"}


def _infer_task_memory(payload: dict, ui_mode: str) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    route_mode = str(payload.get("route_mode") or "")
    classification = str(payload.get("classification") or "")
    changed = payload.get("changed_files") if isinstance(payload.get("changed_files"), list) else []
    writes_files = bool(payload.get("writes_files")) or bool(changed)
    done_criteria = [
        "Intent korrekt geroutet",
        "Antwort/Ergebnis strukturiert geliefert",
    ]
    if writes_files:
        done_criteria.extend(
            [
                "Dateiänderungen nachvollziehbar aufgelistet",
                "Empfohlene Verifikation ausgeführt oder markiert",
            ]
        )
    assumptions = [
        "Workspace- und Berechtigungszustand unverändert",
        "Lokale Toolchain ist verfügbar",
    ]
    return {
        "goal": str(payload.get("task_kind") or payload.get("status") or ui_mode or "direct_run_task"),
        "route_mode": route_mode,
        "classification": classification,
        "writes_files": writes_files,
        "done_criteria": done_criteria,
        "assumptions": assumptions,
    }


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
    ui_mode = str(merged.get("ui_mode") or "")
    merged["recommended_checks"] = _infer_recommended_checks(merged, ui_mode)
    merged["verification_required"] = bool(ui_mode in {"project_change", "repair_task"} and merged.get("writes_files"))
    merged["confidence_gate"] = _infer_confidence(merged, ui_mode)
    merged["task_memory"] = _infer_task_memory(merged, ui_mode)
    # Bei expliziten Datei-Edits (frontend/backend Pfad) kein super_builder-Metadatenblock.
    try:
        sel = str(merged.get("selected_target_path") or "").strip().lower()
        explicit_file_edit = sel.startswith("frontend/") or sel.startswith("backend/")
        if not explicit_file_edit:
            fp = merged.get("file_plan")
            if isinstance(fp, list):
                explicit_file_edit = any(
                    str(x or "").strip().lower().startswith(("frontend/", "backend/")) for x in fp
                )
        if explicit_file_edit:
            merged.pop("super_builder", None)
    except Exception:
        pass
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
