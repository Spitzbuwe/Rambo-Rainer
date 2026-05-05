from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


def _ts() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CloudFacade:
    __slots__ = ("project_root", "data_file")

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.data_file = self.project_root / "data" / "remote_tasks.json"

    def health(self) -> dict[str, Any]:
        state = self._load()
        return {
            "module": "agent_cloud",
            "class": "CloudFacade",
            "ok": True,
            "status": "ready",
            "tasks": len(state.get("tasks") or []),
            "writes_files": False,
        }

    def describe(self) -> str:
        return "Remote/SSH cloud facade (local-safe simulated mode)"

    def _load(self) -> dict[str, Any]:
        if not self.data_file.exists():
            return {"tasks": []}
        try:
            return json.loads(self.data_file.read_text(encoding="utf-8"))
        except Exception:
            return {"tasks": []}

    def _save(self, payload: dict[str, Any]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def start_remote_task(self, prompt: str, host: str = "localhost", use_ssh: bool = True) -> dict[str, Any]:
        state = self._load()
        task_id = f"rmt_{uuid4().hex[:10]}"
        row = {
            "task_id": task_id,
            "prompt": prompt.strip(),
            "host": host.strip() or "localhost",
            "use_ssh": bool(use_ssh),
            "status": "queued",
            "created_at": _ts(),
            "updated_at": _ts(),
            "run_mode": "background",
            "notification_planned": True,
            "result": None,
            "events": [
                {"ts": _ts(), "type": "queued", "message": "Remote task queued."},
            ],
        }
        state.setdefault("tasks", []).append(row)
        self._save(state)
        return {"ok": True, "task": row, "writes_files": False, "auto_commit": False, "auto_rollback": False}

    def list_remote_tasks(self, status: str = "") -> dict[str, Any]:
        rows = list(self._load().get("tasks") or [])
        if status:
            rows = [r for r in rows if str(r.get("status") or "") == status]
        return {"ok": True, "tasks": rows, "count": len(rows), "writes_files": False}

    def resume_remote_task(self, task_id: str) -> dict[str, Any]:
        state = self._load()
        for row in state.get("tasks") or []:
            if str(row.get("task_id")) == str(task_id):
                if str(row.get("status")) in ("done", "failed"):
                    return {"ok": False, "error": "final_state", "task": row}
                row["status"] = "running"
                row["updated_at"] = _ts()
                row.setdefault("events", []).append({"ts": _ts(), "type": "running", "message": "Task resumed."})
                self._save(state)
                return {"ok": True, "task": row, "writes_files": False}
        return {"ok": False, "error": "not_found"}

    def append_event(self, task_id: str, message: str, event_type: str = "progress") -> dict[str, Any]:
        state = self._load()
        for row in state.get("tasks") or []:
            if str(row.get("task_id")) == str(task_id):
                row.setdefault("events", []).append({"ts": _ts(), "type": event_type, "message": message})
                row["updated_at"] = _ts()
                self._save(state)
                return {"ok": True, "task": row}
        return {"ok": False, "error": "not_found"}

    def stream_events(self, task_id: str, limit: int = 50) -> dict[str, Any]:
        for row in self._load().get("tasks") or []:
            if str(row.get("task_id")) == str(task_id):
                events = list(row.get("events") or [])[-max(1, min(int(limit), 500)) :]
                return {"ok": True, "task_id": task_id, "events": events, "status": row.get("status"), "writes_files": False}
        return {"ok": False, "error": "not_found", "task_id": task_id, "events": []}


def get_instance(project_root: Path | str | None = None) -> CloudFacade:
    return CloudFacade(project_root)


__all__ = ["CloudFacade", "get_instance"]
