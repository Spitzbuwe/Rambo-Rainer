from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import jsonify, request

from agent_lsp import diagnostics, find_references, go_to_definition, hover_info, symbols
from agent_intellisense import code_actions, completions, rename_apply, rename_plan, signature_help


def register_cursor_features(app, _socketio=None, _scheduler=None, get_project_root_fn=None):
    pending_hunks: dict[str, dict[str, Any]] = {}
    collab_sessions: dict[str, dict[str, Any]] = {}
    pending_rename_confirmations: dict[str, dict[str, Any]] = {}

    def _root() -> Path:
        return Path(get_project_root_fn()).resolve() if get_project_root_fn else Path(".").resolve()

    plugins_file = (Path(".").resolve() / "data" / "plugins_registry.json").resolve()

    def _load_plugins() -> list[dict[str, Any]]:
        if not plugins_file.exists():
            return []
        try:
            data = json.loads(plugins_file.read_text(encoding="utf-8"))
            return list(data.get("plugins") or [])
        except Exception:
            return []

    def _save_plugins(rows: list[dict[str, Any]]) -> None:
        plugins_file.parent.mkdir(parents=True, exist_ok=True)
        plugins_file.write_text(json.dumps({"plugins": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    plugins: list[dict[str, Any]] = _load_plugins()

    @app.route("/api/lsp/definition", methods=["GET"])
    def lsp_definition():
        out = go_to_definition(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
        return jsonify(out)

    @app.route("/api/lsp/references", methods=["GET"])
    def lsp_references():
        out = find_references(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
        return jsonify(out)

    @app.route("/api/lsp/hover", methods=["GET"])
    def lsp_hover():
        out = hover_info(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
        return jsonify(out)

    @app.route("/api/lsp/symbols", methods=["GET"])
    def lsp_symbols():
        return jsonify(symbols(_root()))

    @app.route("/api/lsp/diagnostics", methods=["GET"])
    def lsp_diagnostics():
        return jsonify(diagnostics(_root(), str(request.args.get("file") or "")))

    @app.route("/api/lsp/completions", methods=["GET"])
    def lsp_completions():
        try:
            out = completions(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
            return jsonify(out), 200
        except PermissionError:
            return jsonify({"ok": False, "error": "forbidden_path", "read_only": True}), 403

    @app.route("/api/lsp/signature", methods=["GET"])
    def lsp_signature():
        try:
            out = signature_help(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
            return jsonify(out), 200
        except PermissionError:
            return jsonify({"ok": False, "error": "forbidden_path", "read_only": True}), 403

    @app.route("/api/lsp/actions", methods=["GET"])
    def lsp_actions():
        try:
            out = code_actions(_root(), str(request.args.get("file") or ""), int(request.args.get("line") or 0), int(request.args.get("col") or 0))
            return jsonify(out), 200
        except PermissionError:
            return jsonify({"ok": False, "error": "forbidden_path", "read_only": True}), 403

    @app.route("/api/lsp/rename/plan", methods=["POST"])
    def lsp_rename_plan():
        data = request.get_json(silent=True) or {}
        try:
            out = rename_plan(
                _root(),
                str(data.get("file") or ""),
                str(data.get("old_symbol") or ""),
                str(data.get("new_symbol") or ""),
                pending_rename_confirmations,
            )
            code = 200 if out.get("ok") else 400
            return jsonify(out), code
        except PermissionError:
            return jsonify({"ok": False, "error": "forbidden_path", "writes_files": False}), 403

    @app.route("/api/lsp/rename/apply", methods=["POST"])
    def lsp_rename_apply():
        data = request.get_json(silent=True) or {}
        token = str(data.get("confirmation_token") or "")
        if not token:
            return jsonify({"ok": False, "error": "confirmation_token_required", "writes_files": False}), 400
        try:
            payload, code = rename_apply(_root(), token, pending_rename_confirmations)
            return jsonify(payload), code
        except PermissionError:
            return jsonify({"ok": False, "error": "forbidden_path", "writes_files": False}), 403

    @app.route("/api/hunks/preview", methods=["POST"])
    def hunks_preview():
        data = request.get_json(silent=True) or {}
        file = str(data.get("file") or "").strip()
        content = str(data.get("content") or "")
        if not file:
            return jsonify({"ok": False, "error": "file_required"}), 400
        p = (_root() / file).resolve()
        if _root() not in p.parents:
            return jsonify({"ok": False, "error": "outside_project_root"}), 403
        old = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
        old_lines = old.splitlines()
        new_lines = content.splitlines()
        hunks = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
        chunk_meta: list[dict[str, Any]] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            chunk_meta.append({"old_start": i1, "old_end": i2, "new_lines": new_lines[j1:j2], "tag": tag})
        token = f"hunk_{uuid4().hex[:12]}"
        pending_hunks[token] = {"file": file, "content": content, "chunk_meta": chunk_meta}
        return jsonify({"ok": True, "token": token, "hunks": hunks[:600], "chunks": chunk_meta, "writes_files": False})

    @app.route("/api/hunks/apply", methods=["POST"])
    def hunks_apply():
        data = request.get_json(silent=True) or {}
        token = str(data.get("token") or "")
        entry = pending_hunks.get(token)
        if not entry:
            return jsonify({"ok": False, "error": "invalid_token"}), 404
        p = (_root() / entry["file"]).resolve()
        if _root() not in p.parents:
            return jsonify({"ok": False, "error": "outside_project_root"}), 403
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(entry["content"], encoding="utf-8")
        pending_hunks.pop(token, None)
        return jsonify({"ok": True, "writes_files": True, "affected_files": [entry["file"]], "auto_commit": False})

    @app.route("/api/hunks/apply-one", methods=["POST"])
    def hunks_apply_one():
        data = request.get_json(silent=True) or {}
        token = str(data.get("token") or "")
        idx = int(data.get("hunk_index") or 0)
        entry = pending_hunks.get(token)
        if not entry:
            return jsonify({"ok": False, "error": "invalid_token"}), 404
        chunks = list(entry.get("chunk_meta") or [])
        if idx < 0 or idx >= len(chunks):
            return jsonify({"ok": False, "error": "hunk_index_out_of_range"}), 400
        p = (_root() / entry["file"]).resolve()
        if _root() not in p.parents:
            return jsonify({"ok": False, "error": "outside_project_root"}), 403
        cur = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        c = chunks[idx]
        start = int(c.get("old_start") or 0)
        end = int(c.get("old_end") or start)
        start = max(0, min(start, len(cur)))
        end = max(start, min(end, len(cur)))
        merged = cur[:start] + list(c.get("new_lines") or []) + cur[end:]
        p.write_text("\n".join(merged) + ("\n" if (p.exists()) else ""), encoding="utf-8")
        return jsonify({"ok": True, "writes_files": True, "affected_files": [entry["file"]], "applied_hunk_index": idx, "auto_commit": False})

    @app.route("/api/collab/session", methods=["POST"])
    def collab_session_start():
        data = request.get_json(silent=True) or {}
        sid = f"col_{uuid4().hex[:10]}"
        collab_sessions[sid] = {"session_id": sid, "title": str(data.get("title") or "Session"), "events": []}
        return jsonify({"ok": True, "session": collab_sessions[sid], "writes_files": False})

    @app.route("/api/collab/sessions", methods=["GET"])
    def collab_sessions_list():
        rows = list(collab_sessions.values())
        return jsonify({"ok": True, "sessions": rows, "count": len(rows), "writes_files": False})

    @app.route("/api/collab/session/<session_id>/event", methods=["POST"])
    def collab_session_event(session_id: str):
        row = collab_sessions.get(session_id)
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        data = request.get_json(silent=True) or {}
        row["events"].append({"type": str(data.get("type") or "note"), "message": str(data.get("message") or "")})
        return jsonify({"ok": True, "session": row, "writes_files": False})

    @app.route("/api/collab/session/<session_id>/events", methods=["GET"])
    def collab_session_events(session_id: str):
        row = collab_sessions.get(session_id)
        if not row:
            return jsonify({"ok": False, "error": "not_found"}), 404
        try:
            limit = int(request.args.get("limit") or 50)
        except Exception:
            limit = 50
        events = list(row.get("events") or [])[-max(1, min(limit, 500)) :]
        return jsonify({"ok": True, "session_id": session_id, "events": events, "count": len(events), "writes_files": False})

    @app.route("/api/plugins", methods=["GET"])
    def plugins_list():
        return jsonify({"ok": True, "plugins": plugins, "count": len(plugins), "writes_files": False})

    @app.route("/api/plugins", methods=["POST"])
    def plugins_register():
        data = request.get_json(silent=True) or {}
        plugin_id = str(data.get("plugin_id") or "").strip()
        if not plugin_id:
            return jsonify({"ok": False, "error": "plugin_id_required"}), 400
        row = {
            "plugin_id": plugin_id,
            "name": str(data.get("name") or plugin_id),
            "enabled": bool(data.get("enabled", True)),
            "capabilities": [str(x) for x in list(data.get("capabilities") or ["read"])],
            "safety_gate": {"writes_files": False, "requires_confirmation": False},
        }
        plugins[:] = [p for p in plugins if p.get("plugin_id") != plugin_id]
        plugins.append(row)
        _save_plugins(plugins)
        return jsonify({"ok": True, "plugin": row, "writes_files": False})

    @app.route("/api/plugins/<plugin_id>/toggle", methods=["POST"])
    def plugins_toggle(plugin_id: str):
        data = request.get_json(silent=True) or {}
        enabled = bool(data.get("enabled"))
        hit = None
        for p in plugins:
            if str(p.get("plugin_id")) == str(plugin_id):
                p["enabled"] = enabled
                hit = p
                break
        if not hit:
            return jsonify({"ok": False, "error": "not_found"}), 404
        _save_plugins(plugins)
        return jsonify({"ok": True, "plugin": hit, "writes_files": False})
