from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

DB_NAME = "rainer_tasks.db"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class AgentScheduler:
    __slots__ = ("project_root", "db_path", "_lock")

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.db_path = (self.project_root / DB_NAME).resolve()
        self._lock = threading.Lock()
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._conn() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result TEXT,
                    branch TEXT,
                    run_id TEXT,
                    worktree_path TEXT
                )
                """
            )
            cols = {r[1] for r in db.execute("PRAGMA table_info(tasks)").fetchall()}
            migrations = {
                "result": "ALTER TABLE tasks ADD COLUMN result TEXT",
                "branch": "ALTER TABLE tasks ADD COLUMN branch TEXT",
                "updated_at": "ALTER TABLE tasks ADD COLUMN updated_at TEXT",
                "run_id": "ALTER TABLE tasks ADD COLUMN run_id TEXT",
                "worktree_path": "ALTER TABLE tasks ADD COLUMN worktree_path TEXT",
            }
            for col, stmt in migrations.items():
                if col not in cols:
                    db.execute(stmt)
            db.commit()

    def add_task(self, prompt: str, branch: str = "", run_id: str = "", worktree_path: str = "") -> str:
        task_id = uuid.uuid4().hex
        now = _now()
        with self._lock, self._conn() as db:
            db.execute(
                "INSERT INTO tasks (id, prompt, status, created_at, updated_at, result, branch, run_id, worktree_path) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, prompt.strip(), "queued", now, now, "", str(branch or "").strip(), str(run_id or "").strip(), str(worktree_path or "").strip()),
            )
            db.commit()
        return task_id

    def set_status(self, task_id: str, status: str, result: dict | None = None) -> bool:
        if status not in {"queued", "running", "waiting", "done", "failed"}:
            return False
        with self._lock, self._conn() as db:
            cur = db.execute("SELECT id FROM tasks WHERE id=?", (task_id,)).fetchone()
            if not cur:
                return False
            db.execute(
                "UPDATE tasks SET status=?, updated_at=?, result=? WHERE id=?",
                (status, _now(), json.dumps(result or {}, ensure_ascii=True), task_id),
            )
            db.commit()
        return True

    def get_task(self, task_id: str) -> dict | None:
        with self._conn() as db:
            row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def list_tasks(self, status: str = "") -> list[dict]:
        with self._conn() as db:
            if status:
                rows = db.execute("SELECT * FROM tasks WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = db.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def health(self) -> dict:
        return {"module": "agent_scheduler", "ok": True, "db_path": str(self.db_path)}


_INSTANCE: AgentScheduler | None = None


def get_instance(project_root: Path | str | None = None) -> AgentScheduler:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentScheduler(project_root)
    return _INSTANCE
