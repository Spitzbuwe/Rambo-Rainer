"""
Etappe 1: DIRECT_EXECUTE_PATH vs SAFE_REVIEW_PATH.

Realstatus-Doku: is_direct_safe("Ändere file.txt eine Zeile") — String oder TaskSpec.
Mini-Phase 1: zusaetzlich flache Dicts (Arbeitsauftrag-API) fuer Tests/Integration.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Union

from task_parser import TaskSpec, parse_user_prompt_to_task_spec


def is_direct_safe_prompt(prompt_text: str) -> bool:
    """Alias: gleiche Semantik wie is_direct_safe(str)."""
    return is_direct_safe(prompt_text)


def _risk_level_for_spec(
    operation: str,
    file_count: int,
    line_count: int,
    has_shell: bool,
    has_secrets: bool,
    has_system: bool,
) -> str:
    """Gleiche Schwellen wie task_parser._risk_level (ohne zyklischen Import)."""
    if has_system or operation == "delete_file" or has_shell or has_secrets:
        return "high"
    if operation in {"mixed_files", "shell", "unknown"}:
        return "high" if operation == "shell" else "medium"
    if file_count > 1 or line_count > 100:
        return "medium"
    return "low"


def task_spec_from_routing_dict(d: Mapping[str, Any]) -> TaskSpec:
    """
    Flaches Task-Dict (Mini-Phase-1-Arbeitsauftrag) -> TaskSpec fuer is_direct_safe.

    Erwartete Keys u.a.: operation, file | files, lines, command, has_secrets, has_system_access
    """
    op_raw = str(d.get("operation") or "").strip().lower()
    files = d.get("files")
    single = d.get("file")
    if isinstance(files, list) and len(files) > 0:
        file_count = len(files)
    elif single:
        file_count = 1
    else:
        file_count = 0

    line_count = int(d.get("lines") or 0)
    has_shell_commands = bool(d.get("command")) or op_raw in {"run_command", "shell"}
    has_secrets = bool(d.get("has_secrets"))
    has_system_access = bool(d.get("has_system_access"))

    if op_raw in {"delete_file", "move_file", "chmod", "rm"}:
        operation = "delete_file" if op_raw == "delete_file" else "unknown"
    elif op_raw == "run_command":
        operation = "shell"
    elif op_raw in {"change_files", "mixed_files"}:
        operation = "mixed_files" if file_count > 1 else "change_file"
    elif op_raw in {"change_file", "create_file", "shell", "unknown"}:
        operation = op_raw
    else:
        operation = "unknown"

    if operation == "mixed_files" and file_count <= 1:
        operation = "change_file" if file_count == 1 else "unknown"

    risk_level = _risk_level_for_spec(
        operation, file_count, line_count, has_shell_commands, has_secrets, has_system_access
    )

    return TaskSpec(
        operation=operation,
        file_count=file_count,
        line_count=line_count,
        has_shell_commands=has_shell_commands,
        has_secrets=has_secrets,
        has_system_access=has_system_access,
        risk_level=risk_level,
    )


def is_direct_safe(task_or_spec: Union[TaskSpec, str, Mapping[str, Any]]) -> bool:
    """
    True nur bei klar kleinem Datei-Edit ohne Shell/Secrets/System/Multi-File.

    Aufruf mit Rohtext-Prompt (str), TaskSpec oder flachem Dict (Tests/API).
    Konservativ bei Unklarheit False.
    """
    if isinstance(task_or_spec, str):
        task_or_spec = parse_user_prompt_to_task_spec(task_or_spec)
    elif isinstance(task_or_spec, Mapping):
        task_or_spec = task_spec_from_routing_dict(task_or_spec)
    if not isinstance(task_or_spec, TaskSpec):
        return False
    if task_or_spec.has_shell_commands or task_or_spec.has_secrets or task_or_spec.has_system_access:
        return False
    if task_or_spec.operation in {"delete_file", "shell", "unknown", "mixed_files"}:
        return False
    if task_or_spec.file_count > 1:
        return False
    if task_or_spec.line_count > 100:
        return False
    if task_or_spec.risk_level != "low":
        return False
    if task_or_spec.operation not in {"change_file", "create_file"}:
        return False
    return True


def routing_path_label(task_spec: TaskSpec) -> str:
    return "DIRECT_EXECUTE_PATH" if is_direct_safe(task_spec) else "SAFE_REVIEW_PATH"
