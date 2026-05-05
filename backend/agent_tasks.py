"""
In-Memory Task-Registry fuer async Agent-Laeufe, Cancel und SSE-Streaming.

Nicht fuer Multi-Instanz-Deployment; pro Flask-Prozess eine Registry in app.config.
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

LogSink = Callable[[dict[str, Any]], None]


class AgentTaskRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}

    def create(
        self,
        task_text: str,
        max_iterations: int,
        cancel_event: threading.Event,
    ) -> str:
        tid = str(uuid.uuid4())
        with self._lock:
            self._tasks[tid] = {
                "id": tid,
                "task": task_text,
                "max_iterations": max_iterations,
                "status": "pending",
                "created": time.time(),
                "finished": None,
                "result": None,
                "error": None,
                "stream_logs": [],
                "cancel_event": cancel_event,
            }
        return tid

    def _get(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            t = self._tasks.get(task_id)
            return dict(t) if t else None

    def get_public(self, task_id: str) -> dict[str, Any] | None:
        """Ohne cancel_event (nicht serialisierbar)."""
        raw = self._get(task_id)
        if not raw:
            return None
        out = {k: v for k, v in raw.items() if k != "cancel_event"}
        return out

    def snapshot_stream(self, task_id: str) -> dict[str, Any] | None:
        """Fuer SSE: Status + Log-Kopie."""
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                return None
            return {"status": t["status"], "stream_logs": list(t["stream_logs"])}

    def get_cancel_event(self, task_id: str) -> threading.Event | None:
        with self._lock:
            t = self._tasks.get(task_id)
            return t.get("cancel_event") if t else None

    def set_status(self, task_id: str, status: str) -> None:
        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["status"] = status

    def append_stream_log(self, task_id: str, entry: dict[str, Any]) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return
            logs: list = self._tasks[task_id]["stream_logs"]
            logs.append(entry)
            if len(logs) > 500:
                del logs[:-500]

    def complete(
        self,
        task_id: str,
        result: dict[str, Any] | None = None,
        *,
        error: str | None = None,
        cancelled: bool = False,
    ) -> None:
        with self._lock:
            if task_id not in self._tasks:
                return
            self._tasks[task_id]["finished"] = time.time()
            self._tasks[task_id]["result"] = result
            self._tasks[task_id]["error"] = error
            if cancelled:
                self._tasks[task_id]["status"] = "cancelled"
            elif error:
                self._tasks[task_id]["status"] = "error"
            else:
                self._tasks[task_id]["status"] = "done"

    def cancel(self, task_id: str) -> bool:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t or t["status"] in ("done", "error", "cancelled"):
                return False
            ev: threading.Event = t["cancel_event"]
            ev.set()
            t["status"] = "cancelling"
            return True

    def make_log_sink(self, task_id: str) -> LogSink:
        def sink(entry: dict[str, Any]) -> None:
            self.append_stream_log(task_id, entry)

        return sink

    def list_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            items = sorted(self._tasks.values(), key=lambda x: x["created"], reverse=True)[:limit]
            return [self.get_public(t["id"]) or {} for t in items if t.get("id")]


def get_registry(app) -> AgentTaskRegistry:
    reg = app.config.get("AGENT_TASK_REGISTRY")
    if reg is None:
        reg = AgentTaskRegistry()
        app.config["AGENT_TASK_REGISTRY"] = reg
    return reg
