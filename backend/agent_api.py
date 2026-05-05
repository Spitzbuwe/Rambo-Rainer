"""
HTTP-API fuer den autonomen Agent (Flask-Blueprint).

Endpunkte: execute (sync/async), plan, estimate, history, status, test, cancel,
retry, logs, stream (SSE), stats, report.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import sys
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from agent_tasks import get_registry
from model_providers import generate_chat_response, is_llm_failure_message
from prompt_routing import chat_reply_canned, classify_user_prompt, has_project_change_intent, unknown_clarification_reply
from intent_enrichment import (
    SUGGESTED_INTENT_ACTIONS,
    apply_user_mode_override,
    compose_augmented_user_message,
    intent_llm_enabled,
    normalize_conversation_history_payload,
    run_llm_intent_refinement,
)

logger = logging.getLogger(__name__)

agent_bp = Blueprint("rainer_autonomous_agent", __name__, url_prefix="")


def _project_root() -> Path:
    raw = current_app.config.get("RAINER_APP_DIR")
    if raw:
        return Path(str(raw)).resolve()
    return Path(".").resolve()


def _shared_executor():
    from agent_executor import AgentExecutor

    ex = current_app.config.get("RAINER_AGENT_EXECUTOR")
    if ex is None:
        ex = AgentExecutor(_project_root())
        current_app.config["RAINER_AGENT_EXECUTOR"] = ex
    return ex


def _formatting_chat_reply(task: str) -> str:
    """Lokales LLM wie im Haupt-Chat; Fallback Kurzantwort."""
    try:
        reply = str(generate_chat_response(task) or "").strip()
    except Exception:
        reply = ""
    if is_llm_failure_message(reply) or not reply:
        return chat_reply_canned(task)
    return reply


def _active_workspace_state() -> tuple[str, bool]:
    try:
        from agent_workspace_sandbox import WorkspaceSandbox

        ws = WorkspaceSandbox(_project_root())
        active = ws.get_active_workspace().get("active") or {}
        return str(active.get("path") or "").strip(), bool(active.get("trusted", False))
    except Exception:
        return "", False


def _brain(
    max_it: int,
    *,
    log_sink=None,
    cancel_event: threading.Event | None = None,
):
    from agent_brain import AgentBrain

    return AgentBrain(
        project_root=_project_root(),
        max_iterations=max_it,
        executor=_shared_executor(),
        log_sink=log_sink,
        cancel_event=cancel_event,
    )


def _run_execute_async(app, task_id: str, task: str, max_it: int) -> None:
    def worker() -> None:
        with app.app_context():
            reg = get_registry(current_app._get_current_object())
            cancel_event = reg.get_cancel_event(task_id)
            if cancel_event is None:
                return
            sink = reg.make_log_sink(task_id)
            reg.set_status(task_id, "running")
            try:
                brain = _brain(max_it, log_sink=sink, cancel_event=cancel_event)
                result = brain.execute_task(task)
                if result.get("cancelled"):
                    reg.complete(task_id, result, cancelled=True)
                elif result.get("success"):
                    reg.complete(task_id, result)
                else:
                    reg.complete(task_id, result, error=str(result.get("error") or "Fehler"))
            except Exception as e:
                logger.exception("async agent task %s", task_id)
                reg.complete(task_id, None, error=str(e))

    threading.Thread(target=worker, daemon=True).start()


@agent_bp.route("/api/agent/execute", methods=["POST"])
def agent_execute():
    """
    POST /api/agent/execute
    JSON: task, max_iterations (1–8), async (bool, optional)
    """
    data = request.get_json(silent=True) or {}
    task = str(data.get("task") or data.get("prompt") or "").strip()
    if not task:
        return jsonify({"ok": False, "success": False, "error": "Kein Task"}), 400
    prompt_kind = classify_user_prompt(task)
    if prompt_kind != "risky_project_task" and has_project_change_intent(task):
        prompt_kind = "project_task"
    um = str(data.get("user_mode") or data.get("intent_mode") or "").strip()
    prompt_kind = apply_user_mode_override(
        prompt_kind,
        um or None,
        is_risky=(prompt_kind == "risky_project_task"),
    )
    hist_snip = normalize_conversation_history_payload(data.get("conversation_history"))
    if prompt_kind == "unknown" and intent_llm_enabled():
        _ref = run_llm_intent_refinement(task, hist_snip)
        if _ref:
            prompt_kind = _ref
    augmented_task = compose_augmented_user_message(task, data)
    if prompt_kind == "chat":
        return jsonify(
            {
                "ok": True,
                "success": True,
                "mode": "chat",
                "status": "chat_response",
                "classification": "chat",
                "formatted_response": _formatting_chat_reply(augmented_task),
                "writes_files": False,
                "requires_confirmation": False,
            }
        ), 200
    if prompt_kind == "unknown":
        u_txt = _formatting_chat_reply(augmented_task)
        if not str(u_txt or "").strip():
            u_txt = unknown_clarification_reply()
        return jsonify(
            {
                "ok": True,
                "success": True,
                "mode": "chat",
                "status": "chat_response",
                "classification": "unknown",
                "route_mode": "intent_clarification",
                "task_kind": "intent_clarification",
                "suggested_intent_actions": list(SUGGESTED_INTENT_ACTIONS),
                "formatted_response": u_txt,
                "writes_files": False,
                "requires_confirmation": False,
            }
        ), 200
    if prompt_kind == "risky_project_task":
        return jsonify(
            {
                "ok": False,
                "success": False,
                "classification": "risky_project_task",
                "error": "Riskante Aktion blockiert.",
                "formatted_response": "⚠️ Diese Aktion ist riskant und bleibt blockiert.",
                "writes_files": False,
                "requires_confirmation": True,
            }
        ), 403
    if prompt_kind == "project_read":
        ro_ws, ro_trusted = _active_workspace_state()
        if not ro_ws or not ro_trusted:
            return jsonify(
                {
                    "ok": False,
                    "success": False,
                    "classification": "project_read",
                    "error": "Workspace nicht freigegeben.",
                    "formatted_response": "Bitte waehle zuerst einen Projektordner aus und gib ihn frei.",
                    "writes_files": False,
                    "requires_confirmation": False,
                }
            ), 403
        import main as app_main

        ro_txt = app_main.build_read_only_project_analysis_reply(
            augmented_task,
            path_inference_source=task,
        )
        return jsonify(
            {
                "ok": True,
                "success": True,
                "mode": "read_only_analysis",
                "status": "chat_response",
                "classification": "project_read",
                "route_mode": "read_only_analysis",
                "formatted_response": ro_txt,
                "writes_files": False,
                "requires_confirmation": False,
            }
        ), 200
    workspace_path, ws_trusted = _active_workspace_state()
    if prompt_kind == "project_task" and (not workspace_path or not ws_trusted):
        return jsonify(
            {
                "ok": False,
                "success": False,
                "classification": "project_task",
                "error": "Workspace nicht freigegeben.",
                "formatted_response": "Bitte waehle zuerst einen Projektordner aus und gib ihn frei.",
                "writes_files": False,
                "requires_confirmation": False,
            }
        ), 403
    try:
        max_it = int(data.get("max_iterations") or 5)
    except (TypeError, ValueError):
        max_it = 5
    max_it = max(1, min(max_it, 8))
    logger.info("agent_execute task_len=%s max_iterations=%s async=%s", len(task), max_it, data.get("async"))

    if bool(data.get("async")):
        reg = get_registry(current_app._get_current_object())
        cancel_event = threading.Event()
        task_id = reg.create(task, max_it, cancel_event)
        _run_execute_async(current_app._get_current_object(), task_id, task, max_it)
        return jsonify(
            {
                "ok": True,
                "success": None,
                "async": True,
                "task_id": task_id,
                "message": "Task gestartet — Status per GET /api/agent/logs/<id> oder SSE /api/agent/stream/<id>",
                "poll": {"logs": f"/api/agent/logs/{task_id}", "stream": f"/api/agent/stream/{task_id}"},
            }
        )

    try:
        brain = _brain(max_it)
        result = brain.execute_task(task)
        ok = bool(result.get("success"))
        payload = {
            "ok": ok,
            "success": ok,
            "result": result,
            "message": "Erfolgreich" if ok else (result.get("error") or "Fehler"),
            "iterations": result.get("iterations"),
            "log": result.get("log") or [],
        }
        logger.info("agent_execute fertig success=%s iterations=%s", ok, result.get("iterations"))
        return jsonify(payload)
    except Exception as e:
        logger.exception("agent_execute")
        return jsonify({"ok": False, "success": False, "error": str(e)}), 500


@agent_bp.route("/api/agent/plan", methods=["POST"])
def agent_plan():
    """POST /api/agent/plan — nur Verstehen + Plan, keine Shell."""
    data = request.get_json(silent=True) or {}
    task = str(data.get("task") or "").strip()
    if not task:
        return jsonify({"ok": False, "error": "Kein Task"}), 400
    try:
        max_it = int(data.get("max_iterations") or 5)
    except (TypeError, ValueError):
        max_it = 5
    max_it = max(1, min(max_it, 8))
    try:
        out = _brain(max_it).plan_task(task)
        ok = bool(out.get("success"))
        return jsonify({"ok": ok, "success": ok, "data": out})
    except Exception as e:
        logger.exception("agent_plan")
        return jsonify({"ok": False, "error": str(e)}), 500


@agent_bp.route("/api/agent/estimate", methods=["POST"])
def agent_estimate():
    """POST /api/agent/estimate — heuristische Komplexitaet/Dauer."""
    data = request.get_json(silent=True) or {}
    task = str(data.get("task") or "").strip()
    if not task:
        return jsonify({"ok": False, "error": "Kein Task"}), 400
    try:
        est = _brain(5).estimate_task(task)
        return jsonify({"ok": True, "estimate": est})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@agent_bp.route("/api/agent/cancel/<task_id>", methods=["POST"])
def agent_cancel(task_id: str):
    """POST /api/agent/cancel/<task_id>"""
    reg = get_registry(current_app._get_current_object())
    if reg.cancel(task_id):
        return jsonify({"ok": True, "task_id": task_id, "message": "Abbruch signalisiert"})
    return jsonify({"ok": False, "error": "Task nicht aktiv oder unbekannt"}), 404


@agent_bp.route("/api/agent/logs/<task_id>", methods=["GET"])
def agent_logs(task_id: str):
    """GET /api/agent/logs/<task_id> — Snapshot inkl. stream_logs."""
    reg = get_registry(current_app._get_current_object())
    rec = reg.get_public(task_id)
    if not rec:
        return jsonify({"ok": False, "error": "Unbekannte task_id"}), 404
    return jsonify({"ok": True, "task": rec})


@agent_bp.route("/api/agent/retry/<task_id>", methods=["POST"])
def agent_retry(task_id: str):
    """POST /api/agent/retry/<task_id> — gleicher Auftrag erneut (neue async-Task-ID)."""
    reg = get_registry(current_app._get_current_object())
    old = reg.get_public(task_id)
    if not old:
        return jsonify({"ok": False, "error": "Unbekannte task_id"}), 404
    task = str(old.get("task") or "").strip()
    if not task:
        return jsonify({"ok": False, "error": "Kein gespeicherter Task-Text"}), 400
    data = request.get_json(silent=True) or {}
    try:
        max_it = int(data.get("max_iterations") or old.get("max_iterations") or 5)
    except (TypeError, ValueError):
        max_it = 5
    max_it = max(1, min(max_it, 8))
    cancel_event = threading.Event()
    new_id = reg.create(task, max_it, cancel_event)
    _run_execute_async(current_app._get_current_object(), new_id, task, max_it)
    return jsonify({"ok": True, "task_id": new_id, "retried_from": task_id})


@agent_bp.route("/api/agent/stream/<task_id>", methods=["GET"])
def agent_stream(task_id: str):
    """GET /api/agent/stream/<task_id> — Server-Sent Events (Log-Zeilen + Abschluss)."""
    app = current_app._get_current_object()

    @stream_with_context
    def gen():
        with app.app_context():
            reg = get_registry(current_app._get_current_object())
            last = 0
            while True:
                snap = reg.snapshot_stream(task_id)
                if not snap:
                    yield "event: error\ndata: " + json.dumps({"error": "unknown task"}) + "\n\n"
                    break
                logs = snap.get("stream_logs") or []
                while last < len(logs):
                    yield "data: " + json.dumps(logs[last], ensure_ascii=False) + "\n\n"
                    last += 1
                st = snap.get("status")
                if st in ("done", "error", "cancelled"):
                    yield "data: " + json.dumps({"event": "done", "status": st}, ensure_ascii=False) + "\n\n"
                    break
                time.sleep(0.35)

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@agent_bp.route("/api/agent/stats", methods=["GET"])
def agent_stats():
    """GET /api/agent/stats — aggregierte Metriken."""
    from agent_brain import get_agent_metrics

    ex = _shared_executor()
    m = get_agent_metrics()
    return jsonify(
        {
            "ok": True,
            "metrics": m,
            "executor": {
                "history_entries": len(ex.execution_history),
                "rate_limit_per_minute": getattr(ex, "max_commands_per_minute", None),
            },
        }
    )


@agent_bp.route("/api/agent/report", methods=["GET"])
def agent_report():
    """GET /api/agent/report — Metriken + letzte Tasks."""
    from agent_brain import get_agent_metrics

    reg = get_registry(current_app._get_current_object())
    return jsonify(
        {
            "ok": True,
            "metrics": get_agent_metrics(),
            "recent_tasks": reg.list_recent(15),
            "executor_tail": _shared_executor().get_execution_history(8),
        }
    )


@agent_bp.route("/api/agent/capabilities", methods=["GET"])
def agent_capabilities():
    return jsonify(
        {
            "ok": True,
            "name": "Rainer Agent",
            "type": "Autonomous AI Developer (lokal)",
            "model": "Ollama (Hybrid Quick/Detailed)",
            "capabilities": [
                "Auftraege verstehen und planen (Ollama)",
                "Shell: Whitelist + argv (kein shell=True), Rate-Limit, optional RAINER_AGENT_SANDBOX",
                "Fehler-Loop, Backoff, Kategorien + Fix-Hinweise",
                "Async Tasks + SSE-Stream, Cancel, Retry",
            ],
            "endpoints": {
                "execute": "POST /api/agent/execute",
                "plan": "POST /api/agent/plan",
                "estimate": "POST /api/agent/estimate",
                "capabilities": "GET /api/agent/capabilities",
                "history": "GET /api/agent/history?limit=10",
                "status": "GET /api/agent/status",
                "test": "POST /api/agent/test",
                "cancel": "POST /api/agent/cancel/<task_id>",
                "logs": "GET /api/agent/logs/<task_id>",
                "retry": "POST /api/agent/retry/<task_id>",
                "stream": "GET /api/agent/stream/<task_id>",
                "stats": "GET /api/agent/stats",
                "report": "GET /api/agent/report",
            },
        }
    )


@agent_bp.route("/api/agent/history", methods=["GET"])
def agent_history():
    try:
        limit = request.args.get("limit", default=10, type=int)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit or 10, 100))
    hist = _shared_executor().get_execution_history(limit=limit)
    return jsonify({"ok": True, "total": len(hist), "history": hist})


@agent_bp.route("/api/agent/status", methods=["GET"])
def agent_status():
    from agent_executor import ALLOWED_EXE_STEMS

    root = _project_root()
    ex = _shared_executor()
    return jsonify(
        {
            "ok": True,
            "online": True,
            "project_root": str(root),
            "executor_history_entries": len(ex.execution_history),
            "allowed_stems": sorted(ALLOWED_EXE_STEMS),
            "sandbox": os.environ.get("RAINER_AGENT_SANDBOX", ""),
        }
    )


@agent_bp.route("/api/agent/test", methods=["POST"])
def agent_test():
    try:
        ex = _shared_executor()
        cmd = f'{sys.executable} -c "print(\'agent_ok\')"'
        r = ex.execute_command(cmd, timeout=30)
        ok = bool(r.get("success")) and "agent_ok" in (r.get("stdout") or "") + (r.get("stderr") or "")
        return jsonify(
            {
                "ok": ok,
                "test": "executor_smoke",
                "executor_result": r,
                "message": "Executor-Self-Test OK" if ok else "Executor-Self-Test fehlgeschlagen",
            }
        )
    except Exception as e:
        logger.exception("agent_test")
        return jsonify({"ok": False, "error": str(e)}), 500


def register_agent_routes(app, project_root: Path) -> None:
    from agent_executor import AgentExecutor

    root = Path(project_root).resolve()
    app.config["RAINER_APP_DIR"] = str(root)
    app.config["RAINER_AGENT_EXECUTOR"] = AgentExecutor(root)
    get_registry(app)
    app.register_blueprint(agent_bp)
    logger.info("register_agent_routes project_root=%s", root)
