from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
import json
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


class FileLockManager:
    def __init__(self) -> None:
        self._mtx = threading.Lock()
        self._locks: dict[str, str] = {}

    def acquire(self, filepath: str, run_id: str) -> bool:
        with self._mtx:
            owner = self._locks.get(filepath)
            if owner and owner != run_id:
                return False
            self._locks[filepath] = run_id
            return True

    def release(self, filepath: str, run_id: str) -> None:
        with self._mtx:
            if self._locks.get(filepath) == run_id:
                self._locks.pop(filepath, None)

    def release_all(self, run_id: str) -> None:
        with self._mtx:
            for fp in list(self._locks.keys()):
                if self._locks.get(fp) == run_id:
                    self._locks.pop(fp, None)

    def get_all_locks(self) -> dict[str, str]:
        with self._mtx:
            return dict(self._locks)


class ParallelAgentManager:
    def __init__(self, project_root: Path | str, max_parallel_runs: int = 4) -> None:
        self.project_root = Path(project_root).resolve()
        self.max_parallel_runs = max_parallel_runs
        self.executor = ThreadPoolExecutor(max_workers=max_parallel_runs)
        self.file_locks = FileLockManager()
        self.runs: dict[str, dict[str, Any]] = {}
        self.conflicts: dict[str, dict[str, Any]] = {}
        self.resolve_tokens: dict[str, dict[str, Any]] = {}

    def _run_task(self, run_id: str) -> None:
        row = self.runs.get(run_id) or {}
        row["status"] = "running"
        row["quality_score"] = row.get("quality_score", 72)
        row["status"] = "done"
        self.runs[run_id] = row

    def start_parallel(self, tasks: list[dict[str, Any]], project_root: Path | str | None = None) -> dict[str, Any]:
        run_ids: list[str] = []
        for t in tasks[: self.max_parallel_runs]:
            run_id = f"par_{uuid4().hex[:10]}"
            row = {
                "run_id": run_id,
                "role": str(t.get("role") or "generic"),
                "task": str(t.get("task") or ""),
                "status": "queued",
                "quality_score": int(t.get("quality_score") or 70),
                "read_files": list(t.get("read_files") or []),
                "write_files": list(t.get("write_files") or []),
                "writes_files": False,
            }
            self.runs[run_id] = row
            run_ids.append(run_id)
            self.executor.submit(self._run_task, run_id)
        self.detect_conflicts()
        return {"ok": True, "run_ids": run_ids}

    def get_status(self) -> dict[str, Any]:
        rows = list(self.runs.values())
        return {"ok": True, "runs": rows, "count": len(rows)}

    def aggregate_results(self, run_ids: list[str]) -> dict[str, Any]:
        rows = [self.runs.get(rid) for rid in run_ids if self.runs.get(rid)]
        best = sorted(rows, key=lambda x: int(x.get("quality_score") or 0), reverse=True)[0] if rows else None
        return {"ok": True, "results": rows, "best_result": best}

    def detect_conflicts(self) -> dict[str, Any]:
        claims: dict[str, list[str]] = {}
        for run_id, row in self.runs.items():
            for fp in list(row.get("write_files") or []):
                claims.setdefault(fp, []).append(run_id)
        self.conflicts = {}
        for fp, owners in claims.items():
            if len(owners) > 1:
                cid = f"cfl_{uuid4().hex[:8]}"
                token = f"cft_{uuid4().hex[:10]}"
                self.conflicts[cid] = {"conflict_id": cid, "file": fp, "run_ids": owners, "status": "conflict", "confirmation_token": token}
                self.resolve_tokens[token] = {"conflict_id": cid, "used": False}
        return {"ok": True, "conflicts": list(self.conflicts.values())}

    def resolve_conflict(self, conflict_id: str, strategy: str, winner_run_id: str, token: str) -> dict[str, Any]:
        t = self.resolve_tokens.get(token)
        if not t or t.get("used") or t.get("conflict_id") != conflict_id:
            return {"ok": False, "error": "invalid_token"}
        row = self.conflicts.get(conflict_id)
        if not row:
            return {"ok": False, "error": "not_found"}
        row["resolution"] = {"strategy": strategy, "winner_run_id": winner_run_id}
        row["status"] = "resolved"
        t["used"] = True
        self.resolve_tokens[token] = t
        self.conflicts[conflict_id] = row
        return {"ok": True, "conflict": row}


class AgentParallelRunner:
    def __init__(self, _project_root: Path | str, max_workers: int = 4) -> None:
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: dict[str, dict[str, Any]] = {}

    def submit_task(self, name: str, fn, timeout_seconds: int | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        tid = f"task-{uuid4().hex[:10]}"
        task = {"task_id": tid, "name": name, "status": "queued", "timeout_seconds": timeout_seconds, "metadata": metadata or {}, "cancel_requested": False}
        fut = self.executor.submit(fn)
        task["future"] = fut
        self.tasks[tid] = task
        return {"ok": True, "task_id": tid}

    def wait(self, task_id: str) -> dict[str, Any]:
        t = self.tasks[task_id]
        fut = t["future"]
        try:
            timeout = t.get("timeout_seconds")
            if timeout is not None and timeout <= 0:
                try:
                    fut.result(timeout=0.001)
                except Exception:
                    t["status"] = "timeout"
                    return {"ok": True, "task": self._sanitize(t)}
            res = fut.result(timeout=(None if timeout is None else max(0.01, float(timeout))))
            try:
                json.dumps(res, ensure_ascii=True)
            except Exception:
                t["status"] = "failed"
                t["error"] = "result_not_json_serializable"
                return {"ok": True, "task": self._sanitize(t)}
            t["result"] = res
            t["status"] = "completed"
        except Exception as e:  # noqa: BLE001
            if t.get("status") != "timeout":
                t["status"] = "failed"
                t["error"] = str(e)
        return {"ok": True, "task": self._sanitize(t)}

    def run_many(self, tasks: list[dict[str, Any]], fail_fast: bool = False, max_workers: int | None = None) -> dict[str, Any]:
        ids = []
        if max_workers and max_workers != self.max_workers:
            self.executor = ThreadPoolExecutor(max_workers=max_workers)
            self.max_workers = max_workers
        fail_fast_triggered = False
        for t in tasks:
            ids.append(self.submit_task(str(t.get("name") or "task"), t.get("fn"))["task_id"])
        results = []
        for tid in ids:
            out = self.wait(tid)["task"]
            results.append(out)
            if fail_fast and out.get("status") == "failed":
                fail_fast_triggered = True
                break
        return {"ok": True, "task_ids": ids, "results": results, "fail_fast_triggered": fail_fast_triggered}

    def cancel(self, task_id: str) -> dict[str, Any]:
        t = self.tasks.get(task_id)
        if not t:
            return {"ok": False, "error": "not_found"}
        t["cancel_requested"] = True
        t["future"].cancel()
        return {"ok": True}

    def status(self, task_id: str | None = None) -> dict[str, Any]:
        if task_id:
            t = self.tasks.get(task_id)
            return {"ok": bool(t), "task": (self._sanitize(t) if t else None)}
        rows = [self._sanitize(t) for t in self.tasks.values()]
        return {"ok": True, "tasks": rows, "stats": self.stats()}

    def results(self) -> dict[str, Any]:
        rows = [self._sanitize(t) for t in self.tasks.values() if t.get("status") in ("completed", "failed", "timeout")]
        return {"ok": True, "tasks": rows}

    def clear_completed(self) -> dict[str, Any]:
        rm = [tid for tid, t in self.tasks.items() if t.get("status") in ("completed", "failed", "timeout")]
        for tid in rm:
            self.tasks.pop(tid, None)
        return {"ok": True, "removed": len(rm)}

    def stats(self) -> dict[str, Any]:
        rows = list(self.tasks.values())
        return {
            "total": len(rows),
            "completed": sum(1 for t in rows if t.get("status") == "completed"),
            "failed": sum(1 for t in rows if t.get("status") == "failed"),
            "timeout": sum(1 for t in rows if t.get("status") == "timeout"),
        }

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "ready", "max_workers": self.max_workers}

    @staticmethod
    def _sanitize(t: dict[str, Any] | None) -> dict[str, Any] | None:
        if not t:
            return None
        out = dict(t)
        out.pop("future", None)
        return out


_INSTANCE: AgentParallelRunner | None = None


def get_instance(project_root: Path | str | None = None) -> AgentParallelRunner:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentParallelRunner(project_root or ".", max_workers=4)
    return _INSTANCE
