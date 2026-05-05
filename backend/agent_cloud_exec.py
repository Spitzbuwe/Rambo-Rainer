from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4


class CloudExecManager:
    def __init__(self, project_root: Path | str) -> None:
        self.project_root = Path(project_root).resolve()
        self.file = self.project_root / "data" / "cloud_exec_jobs.json"
        self.tokens: dict[str, dict[str, Any]] = {}

    def _load(self) -> dict[str, Any]:
        if not self.file.exists():
            return {"jobs": []}
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return {"jobs": []}

    def _save(self, payload: dict[str, Any]) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_providers(self) -> dict[str, Any]:
        return {"ok": True, "providers": [{"id": "github_actions", "available": False}, {"id": "docker_ssh", "available": False}, {"id": "local_simulated", "available": True}]}

    def prepare_job(self, provider: str, task: str, config: dict[str, Any]) -> dict[str, Any]:
        job_id = f"job_{uuid4().hex[:10]}"
        token = f"jobt_{uuid4().hex[:10]}"
        state = self._load()
        row = {"job_id": job_id, "provider": provider, "task": task, "config": config or {}, "status": "planned", "logs": []}
        state.setdefault("jobs", []).append(row)
        self._save(state)
        self.tokens[token] = {"job_id": job_id, "used": False}
        return {"ok": True, "job": row, "confirmation_token": token, "auto_start": False, "result_review_required": True}

    def start_job(self, job_id: str, token: str) -> dict[str, Any]:
        t = self.tokens.get(token)
        if not t or t.get("used") or t.get("job_id") != job_id:
            return {"ok": False, "error": "invalid_token"}
        state = self._load()
        hit = None
        for r in state.get("jobs", []):
            if str(r.get("job_id")) == job_id:
                r["status"] = "running"
                r.setdefault("logs", []).append("job started")
                hit = r
                break
        if not hit:
            return {"ok": False, "error": "not_found"}
        t["used"] = True
        self.tokens[token] = t
        self._save(state)
        return {"ok": True, "job": hit, "external_execution": True, "auto_apply": False, "auto_commit": False, "auto_rollback": False}

    def status(self, job_id: str) -> dict[str, Any]:
        for r in self._load().get("jobs", []):
            if str(r.get("job_id")) == job_id:
                return {"ok": True, "job": r}
        return {"ok": False, "error": "not_found"}

    def logs(self, job_id: str) -> dict[str, Any]:
        st = self.status(job_id)
        if not st.get("ok"):
            return st
        return {"ok": True, "job_id": job_id, "logs": list((st.get("job") or {}).get("logs") or [])}

    def cancel(self, job_id: str) -> dict[str, Any]:
        state = self._load()
        for r in state.get("jobs", []):
            if str(r.get("job_id")) == job_id:
                r["status"] = "canceled"
                r.setdefault("logs", []).append("job canceled")
                self._save(state)
                return {"ok": True, "job": r}
        return {"ok": False, "error": "not_found"}
