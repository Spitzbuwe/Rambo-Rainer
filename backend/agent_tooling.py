from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
import json


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def build_tool_registry() -> list[dict]:
    return [
        {
            "tool_id": "list_project_files",
            "name": "List Project Files",
            "description": "List safe files in APP_DIR.",
            "category": "read",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "allowed": True,
            "requires_confirmation": False,
            "writes_files": False,
            "reads_files": True,
            "runs_process": False,
            "risk_level": "low",
            "allowed_paths": ["backend/**", "frontend/**", "tests/**", "data/**"],
            "forbidden_paths": ["../*", "Downloads/**", "node_modules/**", ".git/**"],
        },
        {
            "tool_id": "read_project_file",
            "name": "Read Project File",
            "description": "Read one safe project file.",
            "category": "read",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
            "output_schema": {"type": "object"},
            "allowed": True,
            "requires_confirmation": False,
            "writes_files": False,
            "reads_files": True,
            "runs_process": False,
            "risk_level": "low",
            "allowed_paths": ["backend/**", "frontend/**", "tests/**", "data/**"],
            "forbidden_paths": ["../*", "Downloads/**", "node_modules/**", ".git/**"],
        },
        {
            "tool_id": "safe_test_runner",
            "name": "Safe Test Runner",
            "description": "Run allowed checks only.",
            "category": "check",
            "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}},
            "output_schema": {"type": "object"},
            "allowed": True,
            "requires_confirmation": False,
            "writes_files": False,
            "reads_files": False,
            "runs_process": True,
            "risk_level": "medium",
            "allowed_paths": ["APP_DIR"],
            "forbidden_paths": ["../*", "Downloads/**"],
            "allowed_commands": ["py_compile_main", "node_check_app", "pytest_all"],
        },
        {
            "tool_id": "validate_patch",
            "name": "Patch Validator",
            "description": "Validates patch preview without writing.",
            "category": "validation",
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "allowed": True,
            "requires_confirmation": False,
            "writes_files": False,
            "reads_files": True,
            "runs_process": False,
            "risk_level": "low",
            "allowed_paths": ["backend/**", "frontend/**", "tests/**", "data/**"],
            "forbidden_paths": ["../*", "Downloads/**", "node_modules/**", ".git/**"],
        },
        {
            "tool_id": "agent_run_apply",
            "name": "Agent Run Apply",
            "description": "Apply confirmed agent run patch via existing flow.",
            "category": "write",
            "input_schema": {"type": "object", "properties": {"confirmation_token": {"type": "string"}}},
            "output_schema": {"type": "object"},
            "allowed": True,
            "requires_confirmation": True,
            "writes_files": True,
            "reads_files": True,
            "runs_process": False,
            "risk_level": "high",
            "allowed_paths": ["backend/**", "frontend/**", "tests/**", "data/**"],
            "forbidden_paths": ["../*", "Downloads/**", "node_modules/**", ".git/**"],
        },
    ]


def get_tool(registry: list[dict], tool_id: str) -> dict | None:
    for t in registry:
        if str(t.get("tool_id")) == str(tool_id):
            return t
    return None


def permission_gate(*, tool: dict | None, payload: dict, app_dir: Path) -> dict:
    p = dict(payload or {})
    warnings = []
    if not isinstance(tool, dict):
        return {"allowed": False, "blocked_reason": "tool_not_found", "risk_level": "high", "requires_confirmation": False, "warnings": warnings, "sanitized_input": {}}
    if not bool(tool.get("allowed")):
        return {"allowed": False, "blocked_reason": "tool_not_allowed", "risk_level": str(tool.get("risk_level") or "high"), "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
    if len(str(p)) > 20000:
        return {"allowed": False, "blocked_reason": "payload_too_large", "risk_level": "medium", "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
    text = str(p).lower()
    if any(x in text for x in ["api_key", "token=", "authorization", "secret"]):
        return {"allowed": False, "blocked_reason": "secret_like_payload", "risk_level": "high", "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
    path = str(p.get("path") or "")
    if path:
        if ".." in path.replace("\\", "/"):
            return {"allowed": False, "blocked_reason": "forbidden_path", "risk_level": "high", "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
        resolved = (app_dir / path).resolve()
        if app_dir not in resolved.parents and resolved != app_dir:
            return {"allowed": False, "blocked_reason": "outside_app_dir", "risk_level": "high", "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
    cmd = str(p.get("command") or "").strip()
    if tool.get("category") == "check":
        allowed_commands = set(tool.get("allowed_commands") or [])
        if cmd and cmd not in allowed_commands:
            return {"allowed": False, "blocked_reason": "command_not_allowed", "risk_level": "high", "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": {}}
    if bool(tool.get("writes_files")) and bool(tool.get("requires_confirmation")) and not str(p.get("confirmation_token") or "").strip():
        return {"allowed": False, "blocked_reason": "confirmation_required", "risk_level": str(tool.get("risk_level") or "high"), "requires_confirmation": True, "warnings": warnings, "sanitized_input": {}}
    return {"allowed": True, "blocked_reason": "", "risk_level": str(tool.get("risk_level") or "low"), "requires_confirmation": bool(tool.get("requires_confirmation")), "warnings": warnings, "sanitized_input": p}


def execute_tool(*, tool: dict, payload: dict, app_dir: Path, call_run_check, call_agent_confirm, load_state) -> dict:
    started = _now()
    t0 = datetime.now()
    tool_id = str(tool.get("tool_id") or "")
    warnings = []
    errors = []
    output = {}
    status = "ok"
    affected_files = []
    try:
        if tool_id == "list_project_files":
            files = []
            for p in app_dir.rglob("*"):
                if p.is_file():
                    rel = str(p.relative_to(app_dir)).replace("\\", "/")
                    if rel.startswith(".git/") or "node_modules/" in rel or rel.startswith("Downloads/"):
                        continue
                    files.append(rel)
                if len(files) >= 400:
                    break
            output = {"files": files}
        elif tool_id == "read_project_file":
            rel = str(payload.get("path") or "").replace("\\", "/")
            target = (app_dir / rel).resolve()
            txt = target.read_text(encoding="utf-8", errors="ignore")[:8000]
            output = {"path": rel, "content": txt}
        elif tool_id == "safe_test_runner":
            output = call_run_check(str(payload.get("command") or ""))
        elif tool_id == "validate_patch":
            plan = list(payload.get("patch_plan") or [])
            blocked = any(".." in str((x or {}).get("file") or "") for x in plan)
            large = len(json.dumps(plan, ensure_ascii=True)) > 20000
            output = {
                "patch_plan": plan,
                "has_changes": any(bool((x or {}).get("has_changes")) for x in plan),
                "validation": {"ok": not blocked and not large, "writes_files": False, "large_patch_blocked": large, "blocked": blocked},
                "safety_review": {"allowed": not blocked and not large, "blocked_reasons": ["forbidden_path"] if blocked else (["large_patch_blocked"] if large else [])},
                "risk": "high" if blocked or large else "low",
                "recommended_checks": ["node_check_app", "py_compile_main"] if any("frontend/" in str((x or {}).get("file") or "") for x in plan) else ["py_compile_main"],
            }
        elif tool_id == "agent_run_apply":
            out, code = call_agent_confirm(str(payload.get("confirmation_token") or ""))
            output = out
            if int(code) >= 400:
                status = "error"
        elif tool_id == "read_git_status":
            output = load_state()
        elif tool_id == "read_memory_summary":
            output = {"ok": True}
        else:
            status = "blocked"
            errors.append("tool_not_implemented")
        affected_files = list(output.get("affected_files") or [])
    except Exception as exc:
        status = "error"
        errors.append(str(exc))
    finished = _now()
    dur = int((datetime.now() - t0).total_seconds() * 1000)
    return {
        "tool_id": tool_id,
        "ok": status == "ok",
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "duration_ms": dur,
        "input_summary": {k: ("<set>" if "token" in k.lower() else v) for k, v in dict(payload or {}).items()},
        "output": output,
        "warnings": warnings,
        "errors": errors,
        "writes_files": bool(tool.get("writes_files")),
        "affected_files": affected_files,
    }


def build_external_tool_adapters() -> dict:
    return {
        "enabled": False,
        "adapters": [
            {
                "tool_id": "external_ollama",
                "adapter_type": "command",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "safety_policy": "disabled_by_default",
                "timeout": 15000,
                "output_limit": 12000,
                "enabled": False,
            }
        ],
    }
