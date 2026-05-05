from __future__ import annotations

from typing import Any
from uuid import uuid4

STEPS = [
    "create_branch_plan",
    "run_safety_check",
    "commit_plan",
    "push_plan",
    "create_pr_draft",
    "request_review_plan",
    "wait_for_approval",
    "final_checks",
    "merge_plan",
    "cleanup_plan",
]


class PRWorkflowManager:
    def __init__(self) -> None:
        self.workflows: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, dict[str, Any]] = {}

    def start(self, payload: dict[str, Any]) -> dict[str, Any]:
        wid = f"wf_{uuid4().hex[:10]}"
        token = f"wft_{uuid4().hex[:10]}"
        row = {
            "workflow_id": wid,
            "status": "running",
            "current_step": STEPS[0],
            "steps": list(STEPS),
            "index": 0,
            "timeline": [{"step": s, "status": ("running" if i == 0 else "pending")} for i, s in enumerate(STEPS)],
            "pr_checks": [
                {"name": "py_compile_main", "status": "pending"},
                {"name": "node_check_app", "status": "pending"},
                {"name": "pytest_all", "status": "pending"},
            ],
        }
        self.workflows[wid] = row
        self.tokens[token] = {"workflow_id": wid, "step_index": 0, "used": False}
        return {"ok": True, **row, "next_step": STEPS[1], "confirmation_token": token, "requires_confirmation": True}

    def status(self, workflow_id: str) -> dict[str, Any]:
        row = self.workflows.get(workflow_id)
        if not row:
            return {"ok": False, "error": "not_found"}
        idx = int(row["index"])
        return {"ok": True, **row, "next_step": (STEPS[idx + 1] if idx + 1 < len(STEPS) else None)}

    def advance(self, workflow_id: str, token: str) -> dict[str, Any]:
        row = self.workflows.get(workflow_id)
        if not row:
            return {"ok": False, "error": "not_found"}
        tk = self.tokens.get(token)
        if not tk or tk.get("used") or tk.get("workflow_id") != workflow_id:
            return {"ok": False, "error": "invalid_token"}
        tk["used"] = True
        idx = int(row["index"]) + 1
        row["index"] = idx
        row["current_step"] = STEPS[min(idx, len(STEPS) - 1)]
        tl = list(row.get("timeline") or [])
        for i, item in enumerate(tl):
            if i < idx:
                item["status"] = "done"
            elif i == idx:
                item["status"] = "running"
            else:
                item["status"] = "pending"
        row["timeline"] = tl
        if row["current_step"] == "final_checks":
            row["pr_checks"] = [
                {"name": "py_compile_main", "status": "passed"},
                {"name": "node_check_app", "status": "passed"},
                {"name": "pytest_all", "status": "passed"},
            ]
        if idx >= len(STEPS) - 1:
            row["status"] = "completed"
        next_token = f"wft_{uuid4().hex[:10]}"
        self.tokens[next_token] = {"workflow_id": workflow_id, "step_index": idx, "used": False}
        self.workflows[workflow_id] = row
        return {"ok": True, **row, "confirmation_token": next_token, "requires_confirmation": True}

    def abort(self, workflow_id: str) -> dict[str, Any]:
        row = self.workflows.get(workflow_id)
        if not row:
            return {"ok": False, "error": "not_found"}
        row["status"] = "aborted"
        self.workflows[workflow_id] = row
        return {"ok": True, **row}
