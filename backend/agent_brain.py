"""
Autonomer Agent-Loop: Plan (Ollama) + sichere Shell-Schritte + Fehler-Feedback.

Erweiterungen: Multi-Pass-Verstehen, heuristische Komplexitaet, Plan-only API,
Fehler-Kategorien + Fix-Hinweise, Backoff zwischen Retries, optionale Log-Sinks,
Cancel-Event, Laufzeit-Metriken.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable

from agent_executor import AgentExecutor
from hybrid_optimizer import hybrid_optimizer

logger = logging.getLogger(__name__)

LogSink = Callable[[dict[str, Any]], None]

_metrics_lock = threading.Lock()
_metrics: dict[str, int | float] = {
    "tasks_started": 0,
    "tasks_ok": 0,
    "tasks_fail": 0,
    "iterations_sum": 0,
    "last_duration_sec": 0.0,
}


def get_agent_metrics() -> dict[str, Any]:
    with _metrics_lock:
        s = dict(_metrics)
    started = max(1, int(s["tasks_started"]))
    ok = int(s["tasks_ok"])
    return {
        **s,
        "success_rate": round(ok / started, 4),
        "avg_iterations": round(float(s["iterations_sum"]) / started, 3),
    }


def _record_metrics(*, ok: bool, iterations: int, duration: float) -> None:
    with _metrics_lock:
        _metrics["tasks_started"] = int(_metrics["tasks_started"]) + 1
        if ok:
            _metrics["tasks_ok"] = int(_metrics["tasks_ok"]) + 1
        else:
            _metrics["tasks_fail"] = int(_metrics["tasks_fail"]) + 1
        _metrics["iterations_sum"] = int(_metrics["iterations_sum"]) + iterations
        _metrics["last_duration_sec"] = duration


class AgentBrain:
    """Verstehen -> Plan -> Ausfuehren -> pruefen; bei Fehler Kontext anreichern."""

    def __init__(
        self,
        project_root: Path | str,
        max_iterations: int = 5,
        executor: AgentExecutor | None = None,
        log_sink: LogSink | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.max_iterations = max(1, min(int(max_iterations), 8))
        self.executor = executor or AgentExecutor(self.project_root)
        self.iteration = 0
        self.task_log: list[dict[str, Any]] = []
        self.log_sink = log_sink
        self.cancel_event = cancel_event

    def _log(self, level: str, message: str) -> None:
        entry = {
            "iteration": self.iteration + 1,
            "level": level,
            "message": message,
            "timestamp": time.time(),
        }
        self.task_log.append(entry)
        logger.info("%s | %s", level, message[:2000])
        if self.log_sink:
            try:
                self.log_sink(entry)
            except Exception:
                logger.exception("log_sink failed")

    def estimate_task(self, task: str) -> dict[str, Any]:
        """Heuristische Schaetzung ohne LLM (schnell fuer /api/agent/estimate)."""
        t = str(task or "").strip()
        if not t:
            return {"ok": False, "error": "Leerer Auftrag"}
        n = len(t)
        words = len(t.split())
        score = min(1.0, (n / 4000.0) * 0.5 + (words / 400.0) * 0.5)
        complexity = "low" if score < 0.25 else "medium" if score < 0.55 else "high"
        est_sec = int(20 + score * 180)
        return {
            "ok": True,
            "complexity": complexity,
            "complexity_score": round(score, 3),
            "estimated_seconds": est_sec,
            "hints": [
                "Kurze Auftraege sind zuverlaessiger",
                "Explizite Dateipfade reduzieren Iterationen",
            ],
        }

    def plan_task(self, task: str) -> dict[str, Any]:
        """Nur Verstehen + Plan — keine Shell-Ausfuehrung."""
        task = str(task or "").strip()
        if not task:
            return {"success": False, "error": "Leerer Auftrag", "log": []}
        self.task_log = []
        self._log("PLAN_ONLY", "Start (ohne Execute)")
        u = self._understand_task(task)
        if not u.get("success"):
            return {"success": False, "error": u.get("error"), "understanding": u, "log": list(self.task_log)}
        u = self._maybe_refine_understanding(task, u)
        self._log("UNDERSTAND_PLAN_ONLY", (u.get("analysis") or "")[:160])
        p = self._make_plan(task, u)
        if not p.get("success"):
            return {
                "success": False,
                "error": p.get("error"),
                "understanding": u,
                "plan": p,
                "log": list(self.task_log),
            }
        cmds = self._parse_commands_from_plan(str(p.get("plan") or ""))
        return {
            "success": True,
            "understanding": u,
            "plan": p,
            "parsed_commands": cmds,
            "command_count": len(cmds),
            "log": list(self.task_log),
        }

    def execute_task(self, task: str) -> dict[str, Any]:
        task = str(task or "").strip()
        if not task:
            return {"success": False, "error": "Leerer Auftrag", "log": []}
        t0 = time.time()
        self.task_log = []
        current = task
        history: list[dict[str, Any]] = []

        self._log("AGENT_START", f"Auftrag (Auszug): {task[:200]}...")
        self._log("STATUS", f"max_iterations={self.max_iterations}")
        self._log("ESTIMATE", str(self.estimate_task(task)))

        for self.iteration in range(self.max_iterations):
            if self.cancel_event and self.cancel_event.is_set():
                self._log("CANCEL", "Abbruch vor Iteration")
                dur = time.time() - t0
                _record_metrics(ok=False, iterations=self.iteration + 1, duration=dur)
                return {
                    "success": False,
                    "error": "Abgebrochen",
                    "cancelled": True,
                    "iterations": self.iteration + 1,
                    "history": history,
                    "log": list(self.task_log),
                }

            if self.iteration > 0:
                delay = min(30.0, 1.5 * (2 ** (self.iteration - 1)))
                self._log("BACKOFF", f"Pause {delay:.1f}s vor Retry")
                time.sleep(delay)

            self._log("ITERATION", f"{self.iteration + 1}/{self.max_iterations}")
            logger.info("Agent iteration %s/%s", self.iteration + 1, self.max_iterations)

            understanding = self._understand_task(current)
            if not understanding.get("success"):
                history.append({"phase": "understand", "iteration": self.iteration + 1, **understanding})
                self._log("ERROR", understanding.get("error") or "Verstehen fehlgeschlagen")
                dur = time.time() - t0
                _record_metrics(ok=False, iterations=self.iteration + 1, duration=dur)
                return {
                    "success": False,
                    "error": understanding.get("error") or "Verstehen fehlgeschlagen",
                    "iterations": self.iteration + 1,
                    "history": history,
                    "log": list(self.task_log),
                }
            understanding = self._maybe_refine_understanding(current, understanding)
            history.append({"phase": "understand", "iteration": self.iteration + 1, **understanding})
            summary = (understanding.get("analysis") or "")[:200]
            self._log("UNDERSTAND_OK", summary or "(keine Kurz-Zusammenfassung)")
            reqs = self._extract_requirements(current)
            if reqs:
                self._log("REQUIREMENTS", ", ".join(reqs[:8]))

            plan = self._make_plan(current, understanding)
            history.append({"phase": "plan", "iteration": self.iteration + 1, **plan})
            if not plan.get("success"):
                self._log("ERROR", plan.get("error") or "Planung fehlgeschlagen")
                dur = time.time() - t0
                _record_metrics(ok=False, iterations=self.iteration + 1, duration=dur)
                return {
                    "success": False,
                    "error": plan.get("error") or "Planung fehlgeschlagen",
                    "iterations": self.iteration + 1,
                    "history": history,
                    "log": list(self.task_log),
                }
            n_cmds = len(self._parse_commands_from_plan(str(plan.get("plan") or "")))
            self._log("PLAN_OK", f"Command:-Zeilen (geplant): {n_cmds}")

            execution = self._execute_plan(plan)
            history.append({"phase": "execute", "iteration": self.iteration + 1, **execution})
            test_result = self._test_execution(execution)
            history.append({"phase": "test", "iteration": self.iteration + 1, **test_result})

            if test_result.get("success"):
                self._log("SUCCESS", f"Alle Schritte OK nach Iteration {self.iteration + 1}")
                dur = time.time() - t0
                _record_metrics(ok=True, iterations=self.iteration + 1, duration=dur)
                return {
                    "success": True,
                    "result": execution,
                    "iterations": self.iteration + 1,
                    "final_status": test_result,
                    "history": history,
                    "log": list(self.task_log),
                    "duration_sec": round(dur, 3),
                }
            err = test_result.get("error") or "Unbekannter Fehler"
            self._log("TEST_FAIL", err[:800])
            cat = test_result.get("category") or "unknown"
            self._log("ERROR_CATEGORY", cat)
            for hint in test_result.get("fix_hints") or []:
                self._log("FIX_HINT", hint[:500])
            logger.warning("Agent iteration failed: %s", err[:500])
            current = f"{task}\n\n[FEHLER VORHERIGE ITERATION]\n{err}\n\nBitte Plan und Commands anpassen und Fehler beheben."
            self._log("RETRY", f"Vorbereitung Iteration {self.iteration + 2}")

        self._log("ABORT", f"Max. Iterationen ({self.max_iterations}) erreicht")
        dur = time.time() - t0
        _record_metrics(ok=False, iterations=self.max_iterations, duration=dur)
        return {
            "success": False,
            "error": f"Max. Iterationen ({self.max_iterations}) erreicht",
            "iterations": self.max_iterations,
            "history": history,
            "log": list(self.task_log),
            "duration_sec": round(dur, 3),
        }

    def _maybe_refine_understanding(self, task: str, u: dict[str, Any]) -> dict[str, Any]:
        if len(task) < 320:
            return u
        prompt = (
            "Kompaktiere und schaerfe die folgende Analyse (max. 12 Zeilen, Deutsch).\n"
            "Fokus: Reihenfolge der Arbeitsschritte, Abhaengigkeiten, Rollback-Idee bei Fehlschlag.\n\n"
            f"Analyse:\n{u.get('analysis', '')[:8000]}"
        )
        try:
            r = hybrid_optimizer.execute_optimized(
                prompt,
                context="",
                system_prompt="Du bist ein kritischer Architekt — nur Text, keine Shell.",
            )
        except Exception:
            return u
        if not r.get("success"):
            return u
        refined = str(r.get("response") or "").strip()
        if len(refined) < 20:
            return u
        out = dict(u)
        out["analysis"] = (out.get("analysis") or "") + "\n\n--- REFINE ---\n" + refined[:6000]
        out["refined"] = True
        self._log("REFINE", "Zweite Analyse-Pass abgeschlossen")
        return out

    def _extract_requirements(self, task: str) -> list[str]:
        lines = [ln.strip() for ln in task.splitlines() if ln.strip()]
        bullets = [ln.lstrip("-*• ").strip() for ln in lines if ln.startswith(("-", "*", "•"))]
        return bullets[:20] if bullets else [task[:120]]

    def _understand_task(self, task: str) -> dict[str, Any]:
        prompt = (
            "Analysiere die Aufgabe knapp auf Deutsch.\n\n"
            f"{task}\n\n"
            "Antworte mit: Ziel, noetige Schritte, betroffene Bereiche (backend/frontend), Risiken.\n"
            "Optional eine Zeile: Prioritaet: hoch|mittel|niedrig"
        )
        try:
            result = hybrid_optimizer.execute_optimized(
                prompt,
                context="",
                system_prompt=(
                    "Du bist ein Planungs-Agent fuer ein lokales Softwareprojekt. "
                    "Nur Analyse und Plan — keine Shell-Befehle selbst ausfuehren."
                ),
            )
        except Exception as e:
            logger.exception("_understand_task")
            return {"success": False, "error": str(e), "analysis": ""}
        if not result.get("success"):
            return {
                "success": False,
                "error": result.get("error") or "Ollama fehlgeschlagen",
                "analysis": "",
            }
        return {
            "success": True,
            "analysis": str(result.get("response") or "")[:12000],
            "model": result.get("model", ""),
        }

    def _make_plan(self, task: str, understanding: dict[str, Any]) -> dict[str, Any]:
        analysis = str(understanding.get("analysis") or "")
        prompt = (
            "Erstelle einen strukturierten Plan (Markdown) fuer die Umsetzung.\n"
            "Beruecksichtige Abhaengigkeiten: zuerst install/build, dann Tests.\n"
            "Falls sinnvoll, kurz notieren welche Schritte parallelisierbar waeren (nur Text).\n\n"
            f"Auftrag:\n{task}\n\n"
            f"Analyse:\n{analysis}\n\n"
            "Fuer jeden ausfuehrbaren Schritt eine Zeile exakt im Format:\n"
            "Command: <ein einzelner Befehl, z.B. python -m py_compile backend/main.py>\n\n"
            "Erlaubte Programme u. a.: python, py, pip, npm, npx, node, git, pytest, cargo, ruff, uv, poetry.\n"
            "Keine Shell-Ketten, keine Pipes."
        )
        try:
            result = hybrid_optimizer.execute_optimized(
                prompt,
                context="",
                system_prompt="Du erzeugst nur Plaene — ein Command pro Zeile nach dem Marker Command:",
            )
        except Exception as e:
            logger.exception("_make_plan")
            return {"success": False, "error": str(e), "plan": ""}
        if not result.get("success"):
            return {"success": False, "error": result.get("error"), "plan": ""}
        return {
            "success": True,
            "plan": str(result.get("response") or "")[:16000],
            "model": result.get("model", ""),
        }

    def _execute_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        plan_text = str(plan.get("plan") or "")
        commands = self._parse_commands_from_plan(plan_text)
        results: list[dict[str, Any]] = []
        for cmd in commands:
            logger.info("Execute: %s", cmd[:200])
            self._log("EXECUTE", cmd[:500])
            r = self.executor.execute_command(cmd)
            results.append(r)
        return {
            "commands_executed": len(commands),
            "commands": commands,
            "results": results,
            "all_success": bool(results) and all(r.get("success") for r in results),
        }

    def _classify_stderr(self, text: str) -> str:
        low = (text or "").lower()
        if "syntaxerror" in low or "indentationerror" in low:
            return "syntax"
        if "modulenotfounderror" in low or "importerror" in low or "cannot find module" in low:
            return "import"
        if "pytest" in low or "assert" in low or "failures" in low:
            return "test"
        if "npm err" in low or "enoent" in low or "404" in low:
            return "network_or_registry"
        if "permission denied" in low or "eperm" in low:
            return "permission"
        return "generic"

    def _fix_hints(self, category: str, stderr: str) -> list[str]:
        snippets = (stderr or "")[:400]
        base = {
            "syntax": ["Datei mit python -m py_compile pruefen", "Syntaxzeile laut Traceback oeffnen"],
            "import": ["pip install / poetry add pruefen", "PYTHONPATH bzw. cwd pruefen"],
            "test": ["Einzeltest mit pytest -k ausfuehren", "Fixture-Abhaengigkeiten pruefen"],
            "network_or_registry": ["Proxy/Offline pruefen", "npm cache clean --force (vorsicht)"],
            "permission": ["Datei schreibbar?", "Antivirus/Ordnerrechte pruefen"],
            "generic": ["Befehl manuell im Projektroot wiederholen", "stderr vollstaendig lesen"],
        }
        hints = list(base.get(category, base["generic"]))
        if snippets:
            hints.append(f"Auszug stderr: {snippets[:200]}")
        return hints[:6]

    def _test_execution(self, execution: dict[str, Any]) -> dict[str, Any]:
        if not execution.get("results"):
            return {
                "success": False,
                "error": "Keine Commands aus dem Plan ausfuehrbar (keine Command:-Zeilen?).",
                "category": "no_commands",
                "fix_hints": ["Plan muss Zeilen mit Command: enthalten", "Modell erneut fragen"],
            }
        if execution.get("all_success"):
            return {"success": True, "message": "Alle Commands erfolgreich."}
        errors = []
        worst_cat = "generic"
        merged_stderr = ""
        for r in execution.get("results") or []:
            if r.get("success"):
                continue
            msg = r.get("stderr") or r.get("error") or str(r.get("returncode"))
            merged_stderr += str(msg) + "\n"
            errors.append(str(msg)[:2000])
            worst_cat = self._classify_stderr(str(msg))
        return {
            "success": False,
            "error": "\n".join(errors)[:8000],
            "category": worst_cat,
            "fix_hints": self._fix_hints(worst_cat, merged_stderr),
        }

    def _parse_commands_from_plan(self, plan_text: str) -> list[str]:
        commands: list[str] = []
        for line in plan_text.splitlines():
            m = re.search(r"(?i)command:\s*(.+)$", line.strip())
            if m:
                cmd = m.group(1).strip().strip("`").strip()
                if cmd:
                    commands.append(cmd)
        return commands[:12]
