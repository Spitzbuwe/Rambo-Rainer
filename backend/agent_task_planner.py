from __future__ import annotations

from datetime import datetime


class TaskPlannerAgent:
    def __init__(self):
        self.max_steps = 8

    def _infer_focus(self, task: str) -> str:
        t = str(task or "").lower()
        if "frontend" in t or "ui" in t:
            return "frontend"
        if "backend" in t or "api" in t:
            return "backend"
        if "test" in t or "pytest" in t:
            return "tests"
        return "general"

    def build_plan(self, task: str, *, risk: str = "medium") -> dict:
        text = str(task or "").strip()
        if not text:
            return {"ok": False, "error": "task fehlt."}
        focus = self._infer_focus(text)
        steps = [
            {"id": "analyze", "label": "Aufgabe analysieren", "writes_files": False, "requires_confirmation": False},
            {"id": "context", "label": "Relevanten Kontext sammeln", "writes_files": False, "requires_confirmation": False},
            {"id": "plan", "label": "Änderungsplan in kleine Schritte zerlegen", "writes_files": False, "requires_confirmation": False},
            {"id": "patch", "label": "Kleinen Patch vorbereiten", "writes_files": True, "requires_confirmation": True},
            {"id": "validate", "label": "Patch prüfen", "writes_files": False, "requires_confirmation": False},
            {"id": "test", "label": "Erlaubte Tests ausführen", "writes_files": False, "requires_confirmation": True},
            {"id": "review", "label": "Ergebnis reviewen", "writes_files": False, "requires_confirmation": False},
        ]
        return {
            "ok": True,
            "mode": "task_plan",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "task": text,
            "focus": focus,
            "risk": str(risk or "medium"),
            "step_count": len(steps),
            "steps": steps[: self.max_steps],
            "safe_to_auto_apply": False,
            "notes": "Plan ist in kleine sichere Schritte aufgeteilt.",
        }


_INSTANCE: TaskPlannerAgent | None = None


def get_instance() -> TaskPlannerAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = TaskPlannerAgent()
    return _INSTANCE
