# -*- coding: utf-8 -*-
"""AgentExecutor: Schreibaktionen nur unter outbox/. App.css/App.jsx werden gegen kanonische frontend/src-Pfade gesperrt."""

import os
import json
import sys
import subprocess

AGENT_NAME = "Rambo Rainer"
USER_NAME = "Matze Müller"

ERROR_CLASSES = (
    "syntax_error",
    "import_error",
    "runtime_error",
    "build_error",
    "lint_error",
    "prohibited_file",
    "frontend_write_locked",
    "invalid_path_placeholder",
    "error_loop",
    "unknown_error",
)


def classify_tool_error(message):
    """Grobe Fehlerart aus Freitext (Executor/Build-Logs)."""
    m = str(message or "").lower()
    if not m.strip():
        return "unknown_error"
    if "placeholder" in m or "<" in m and ">" in m:
        return "invalid_path_placeholder"
    if "frontend_write_locked" in m or "app.jsx" in m and "gesperrt" in m:
        return "frontend_write_locked"
    if "prohibited" in m or "verboten" in m:
        return "prohibited_file"
    if "cannot find module" in m or "module not found" in m or "err_module_not_found" in m:
        return "import_error"
    if "syntaxerror" in m or "unexpected token" in m:
        return "syntax_error"
    if "eslint" in m or "lint" in m:
        return "lint_error"
    if "build" in m or "vite" in m or "rollup" in m:
        return "build_error"
    if "timeout" in m or "econnrefused" in m:
        return "runtime_error"
    return "unknown_error"


class AgentExecutor:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.outbox = os.path.join(self.base_path, "outbox")
        self.knowledge = os.path.join(self.base_path, "knowledge")

    def _is_frontend_write_forbidden(self, abs_path):
        """Gleiche Ziele wie server.py: frontend/src/App.css|App.jsx — nie durch Executor beschreiben."""
        try:
            n = os.path.normcase(os.path.normpath(os.path.abspath(abs_path)))
        except Exception:
            return False
        try:
            dash_src = os.path.normcase(
                os.path.normpath(os.path.join(self.base_path, "frontend", "src"))
            )
        except Exception:
            return False
        explicit = []
        try:
            explicit.append(
                os.path.normcase(os.path.normpath(os.path.join(self.base_path, "frontend", "src", "App.css")))
            )
            explicit.append(
                os.path.normcase(os.path.normpath(os.path.join(self.base_path, "frontend", "src", "App.jsx")))
            )
        except Exception:
            pass
        if n in frozenset(explicit):
            return True
        for name in ("App.css", "App.jsx"):
            if n == os.path.normcase(os.path.normpath(os.path.join(dash_src, name))):
                return True
        return False

    def _safe_outbox_path(self, rel_path):
        rel = os.path.normpath(str(rel_path or "").strip()).lstrip(os.sep)
        if not rel or rel.startswith(".."):
            return None
        full = os.path.abspath(os.path.join(self.outbox, rel))
        out_abs = os.path.abspath(self.outbox)
        if full == out_abs or full.startswith(out_abs + os.sep):
            return full
        return None

    def _extract_json_object(self, text):
        s = str(text or "")
        start = s.find("{")
        if start < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        quote = None
        for i in range(start, len(s)):
            ch = s[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    in_str = False
                    quote = None
                continue
            if ch in "\"'":
                in_str = True
                quote = ch
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
        return None

    def execute(self, ai_output):
        logs = []
        try:
            os.makedirs(self.outbox, exist_ok=True)
            os.makedirs(self.knowledge, exist_ok=True)
            blob = self._extract_json_object(ai_output)
            if not blob:
                return ["Kein gültiges JSON-Objekt gefunden."]
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                return ["JSON konnte nicht gelesen werden."]
            if not isinstance(data, dict):
                return ["Ungültiges Aufgabenformat."]
            steps = data.get("steps")
            if steps is None:
                return ["Keine Schritte übermittelt."]
            if not isinstance(steps, list):
                return ["Schritte müssen eine Liste sein."]

            for step in steps:
                if not isinstance(step, dict):
                    logs.append("Schritt übersprungen: kein Objekt.")
                    continue
                action = step.get("action")
                path = step.get("path", "")
                content = step.get("content", "")

                if action == "create_file":
                    full_path = self._safe_outbox_path(path)
                    if not full_path:
                        logs.append("create_file: Pfad ungültig.")
                        continue
                    try:
                        real_target = os.path.normcase(os.path.normpath(os.path.realpath(full_path)))
                    except Exception:
                        real_target = full_path
                    if self._is_frontend_write_forbidden(full_path) or self._is_frontend_write_forbidden(
                        real_target
                    ):
                        logs.append("Frontend-Schreibzugriff gesperrt (App.jsx/App.css).")
                        continue
                    parent = os.path.dirname(full_path)
                    if parent:
                        os.makedirs(parent, exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(str(content))
                    logs.append(f"Datei erstellt: {path}")

                elif action == "write_note":
                    note_path = os.path.join(self.knowledge, "user_notes.md")
                    with open(note_path, "a", encoding="utf-8") as f:
                        f.write(f"\n- {content}")
                    logs.append("Notiz gespeichert.")

                elif action == "open_folder":
                    try:
                        if sys.platform == "win32":
                            os.startfile(self.outbox)  # type: ignore[attr-defined]
                        else:
                            subprocess.run(["xdg-open", self.outbox], check=False)
                        logs.append("Ordner geöffnet.")
                    except Exception as exc:
                        logs.append(f"Ordner: {exc}")
        except Exception as e:
            logs.append(f"Executor-Fehler: {str(e)}")
        return logs
