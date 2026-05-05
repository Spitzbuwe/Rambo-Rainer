"""Agent Task Delegator — Level 8.6.

Decomposes large tasks into sub-tasks for specialist agents.
Enforces:
  - No parallel writes (write gate)
  - No conflicting patches (one consolidated patch plan)
  - Capability checking per role
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from uuid import uuid4

from agent_capability_gate import (
    check_capability,
    get_capabilities,
    is_read_only,
)
from agent_write_gate import AgentWriteGate, get_instance as get_write_gate


# Ordered pipeline: planner first, commit last
DELEGATION_PIPELINE: Tuple[str, ...] = (
    "planner",
    "memory",
    "context",
    "patch",
    "safety",
    "test",
    "review",
    "commit",
)

_TASK_TEMPLATES: dict[str, Tuple[str, str]] = {
    "planner": (
        "Aufgabe zerlegen: {task}",
        "Schritte und Kandidaten-Dateien",
    ),
    "memory": (
        "Frühere Fehler und Patches zu: {task}",
        "Ähnliche Fehler und Hinweise aus der History",
    ),
    "context": (
        "Relevante Dateien lesen{files_hint}",
        "Dateikontexte und Code-Analyse",
    ),
    "patch": (
        "Konsolidierten Patch-Plan erstellen für: {task}",
        "Patch-Plan (kein Write, kein Apply)",
    ),
    "safety": (
        "Risiko und Safety-Gate prüfen",
        "can_apply, blocking_reasons",
    ),
    "test": (
        "Checks empfehlen",
        "recommended_checks",
    ),
    "review": (
        "Ergebnis zusammenfassen",
        "review_summary, next_action",
    ),
    "commit": (
        "Commit-Vorschlag vorbereiten (kein Commit ausführen)",
        "suggested_commit_message (commit_performed=false)",
    ),
}


@dataclass
class DelegatedTask:
    agent_id: str
    role: str
    task: str
    expected_output: str
    trace_id: str = ""
    status: str = "pending"
    result_summary: str = ""
    blocked_by: str = ""
    capabilities: dict = field(default_factory=dict)
    parallel_allowed: bool = False

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "trace_id": self.trace_id,
            "role": self.role,
            "task": self.task,
            "expected_output": self.expected_output,
            "status": self.status,
            "result_summary": self.result_summary,
            "blocked_by": self.blocked_by,
            "capabilities": self.capabilities,
            "parallel_allowed": self.parallel_allowed,
        }


class AgentTaskDelegator:
    """
    Orchestrates specialist agents for a given task.

    Usage:
        d = AgentTaskDelegator()
        tasks = d.decompose("Verbessere den Apply-Flow", ["backend/main.py"])
        read_result = d.execute_read_phase(...)
        patch_result = d.execute_patch_phase(patch_plan)
        safety_result = d.execute_safety_phase(can_apply=True)
        result = d.build_result(review_summary, commit_message)
    """

    def __init__(self, run_id: Optional[str] = None) -> None:
        self.run_id = run_id or str(uuid4())
        self._lock = threading.Lock()
        self._tasks: List[DelegatedTask] = []
        self._write_gate: AgentWriteGate = get_write_gate()
        self._patch_plan: list = []
        self._safety_result: dict = {}
        self._memory_hints: list = []
        self._context_files: list = []
        self._test_checks: list = []
        self._review_summary: str = ""
        self._commit_plan: dict = {}
        self._review_gate: dict = {"approved": True, "blocking_reasons": [], "review_gate_passed": True}

    # ------------------------------------------------------------------
    # 8.6: Task Decomposition
    # ------------------------------------------------------------------

    def decompose(
        self,
        task: str,
        candidate_files: Optional[list] = None,
    ) -> list:
        """Build the delegated task list from a task description."""
        files_hint = candidate_files or []
        files_str = ": " + ", ".join(str(f) for f in files_hint[:5]) if files_hint else ""

        tasks: List[DelegatedTask] = []
        for role in DELEGATION_PIPELINE:
            tmpl_task, tmpl_out = _TASK_TEMPLATES[role]
            task_text = tmpl_task.format(
                task=str(task)[:120],
                files_hint=files_str,
            )
            dt = DelegatedTask(
                agent_id=f"{role}-{self.run_id[:8]}",
                trace_id=f"tr-{role[:4]}-{uuid4().hex[:8]}",
                role=role,
                task=task_text,
                expected_output=tmpl_out,
                capabilities=get_capabilities(role),
                parallel_allowed=is_read_only(role),
            )
            tasks.append(dt)

        with self._lock:
            self._tasks = tasks

        return [t.to_dict() for t in tasks]

    # ------------------------------------------------------------------
    # 8.7: Parallel read phase (read-only agents, no write gate needed)
    # ------------------------------------------------------------------

    def execute_read_phase(
        self,
        task: str,
        memory_hints: Optional[list] = None,
        context_files: Optional[list] = None,
    ) -> dict:
        """Run all read-only agents. No write gate acquired."""
        with self._lock:
            self._memory_hints = list(memory_hints or [])
            self._context_files = list(context_files or [])

        done_ids: list = []
        blocked_ids: list = []

        for dt in self._tasks:
            if dt.role not in ("planner", "memory", "context", "safety", "test", "review"):
                continue
            primary_cap = "can_plan" if dt.role == "planner" else "can_read"
            allowed, msg = check_capability(dt.role, primary_cap)
            if allowed:
                dt.status = "done"
                dt.result_summary = self._default_read_result(dt.role, task)
                done_ids.append(dt.agent_id)
            else:
                dt.status = "blocked"
                dt.blocked_by = msg
                blocked_ids.append(dt.agent_id)

        return {
            "run_id": self.run_id,
            "read_agents_done": done_ids,
            "read_agents_blocked": blocked_ids,
            "memory_hints": self._memory_hints,
            "context_files": self._context_files,
            "parallel_safe": True,
        }

    # ------------------------------------------------------------------
    # Patch phase (creates plan, does NOT write)
    # ------------------------------------------------------------------

    def execute_patch_phase(self, patch_plan: Optional[list] = None) -> dict:
        """PatchAgent creates a consolidated patch plan. No actual write."""
        dt = self._find("patch")

        # Must be able to create patches but NOT write
        ok_create, msg_create = check_capability("patch", "can_create_patch")
        if not ok_create:
            if dt:
                dt.status = "blocked"
                dt.blocked_by = msg_create
            return {"ok": False, "error": msg_create}

        # Guard: patch role must not be able to write
        ok_write, _ = check_capability("patch", "can_write")
        if ok_write:
            msg = "PatchAgent darf nicht direkt schreiben"
            if dt:
                dt.status = "blocked"
                dt.blocked_by = msg
            return {"ok": False, "error": msg}

        with self._lock:
            self._patch_plan = list(patch_plan or [])

        if dt:
            dt.status = "done"
            dt.result_summary = f"{len(self._patch_plan)} Patch(es) vorbereitet (kein Write)"

        return {"ok": True, "patch_plan": self._patch_plan, "writes_performed": False}

    # ------------------------------------------------------------------
    # Safety phase
    # ------------------------------------------------------------------

    def execute_safety_phase(
        self,
        can_apply: bool,
        blocking_reasons: Optional[list] = None,
    ) -> dict:
        dt = self._find("safety")
        with self._lock:
            self._safety_result = {
                "can_apply": bool(can_apply),
                "blocking_reasons": list(blocking_reasons or []),
            }
        if dt:
            if can_apply:
                dt.status = "done"
                dt.result_summary = "Safety ok"
            else:
                dt.status = "blocked"
                reasons = "; ".join(blocking_reasons or ["unbekannt"])
                dt.result_summary = f"Blockiert: {reasons}"
                dt.blocked_by = reasons
        return dict(self._safety_result)

    # ------------------------------------------------------------------
    # 8.7: Write gate — only apply agent can acquire
    # ------------------------------------------------------------------

    def execute_review_gate(
        self,
        approved: bool,
        blocking_reasons: Optional[list] = None,
    ) -> dict:
        """
        Review Gate (8.5) — ReviewAgent can block the run.
        Returns review_gate dict; if not approved, blocks the run.
        """
        dt = self._find("review")
        reasons = list(blocking_reasons or [])
        gate = {
            "approved": bool(approved),
            "blocking_reasons": reasons,
            "review_gate_passed": bool(approved),
        }
        if dt:
            if approved:
                dt.status = "done"
                dt.result_summary = "Review-Gate: freigegeben"
            else:
                dt.status = "blocked"
                dt.blocked_by = "; ".join(reasons) or "Review verweigert"
                dt.result_summary = f"Review-Gate blockiert: {dt.blocked_by}"
        with self._lock:
            self._review_gate = gate
        return gate

    def acquire_write_token(self) -> Tuple[str, bool, str]:
        """
        ApplyAgent acquires the write gate.
        Returns (token, success, message).
        """
        ok, msg = check_capability("apply", "can_apply_patch")
        if not ok:
            return "", False, msg
        return self._write_gate.acquire_write_token(self.run_id)

    def validate_and_consume_token(self, token: str) -> Tuple[bool, str]:
        return self._write_gate.validate_and_consume(token, self.run_id)

    # ------------------------------------------------------------------
    # Build final result
    # ------------------------------------------------------------------

    def build_result(
        self,
        review_summary: str = "",
        commit_message: str = "",
        test_checks: Optional[list] = None,
    ) -> dict:
        """Consolidate all agent results into the final delegation output."""
        with self._lock:
            self._review_summary = str(review_summary or "")
            self._test_checks = list(test_checks or [])
            self._commit_plan = {
                "suggested_commit_message": str(commit_message or ""),
                "commit_performed": False,
            }

        for dt in self._tasks:
            if dt.role == "review" and dt.status == "pending":
                dt.status = "done"
                dt.result_summary = review_summary or "Review abgeschlossen"
            if dt.role == "commit" and dt.status == "pending":
                dt.status = "done"
                dt.result_summary = commit_message or "Commit-Vorschlag erstellt"
            if dt.role == "test" and dt.status == "pending":
                dt.status = "done"
                dt.result_summary = ", ".join(self._test_checks) or "Keine Checks empfohlen"

        return {
            "run_id": self.run_id,
            "delegated_tasks": [t.to_dict() for t in self._tasks],
            "patch_plan": self._patch_plan,
            "safety_result": self._safety_result,
            "review_gate": self._review_gate,
            "test_checks": self._test_checks,
            "review_summary": self._review_summary,
            "commit_plan": self._commit_plan,
            "write_gate_busy": self._write_gate.is_busy,
            "writes_performed": False,
            "auto_commit": False,
            "auto_rollback": False,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find(self, role: str) -> Optional[DelegatedTask]:
        for t in self._tasks:
            if t.role == role:
                return t
        return None

    @staticmethod
    def _default_read_result(role: str, task: str) -> str:
        if role == "planner":
            return f"Plan erstellt für: {str(task)[:60]}"
        if role == "memory":
            return "Keine ähnlichen Fehler in der History"
        if role == "context":
            return "Dateien analysiert"
        if role == "safety":
            return "Safety-Prüfung vorbereitet"
        if role == "test":
            return "Checks empfohlen"
        if role == "review":
            return "Review abgeschlossen"
        return "Ergebnis bereit"

    @property
    def tasks(self) -> list:
        return [t.to_dict() for t in self._tasks]


__all__ = ["AgentTaskDelegator", "DELEGATION_PIPELINE"]
