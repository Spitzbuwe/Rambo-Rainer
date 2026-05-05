# -*- coding: utf-8 -*-
"""Flask Blueprints und Route-Helfer fuer Rambo-Rainer."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Optional

from routing import routing_path_label
from task_parser import TaskSpec, parse_user_prompt_to_task_spec
from write_action import run_write_action_with_watchdog


def persist_text_file_change(
    resolved: Path,
    proposed_content: str,
    display_path: str,
    *,
    timeout_sec: Optional[float] = None,
    on_timeout_log: Optional[Callable[[str], None]] = None,
    backup: bool = True,
    cleanup_success_backup: bool = True,
):
    """Geschuetzter Text-Write (Watchdog)."""
    return run_write_action_with_watchdog(
        resolved,
        proposed_content,
        display_path,
        timeout_sec=timeout_sec,
        on_timeout_log=on_timeout_log,
        backup=backup,
        cleanup_success_backup=cleanup_success_backup,
    )


def handle_user_prompt_routing(prompt_text: str) -> tuple[str, TaskSpec]:
    """Leitet Prompt auf DIRECT/SAFE-Routing anhand Task-Spec."""
    task_spec = parse_user_prompt_to_task_spec(prompt_text)
    label = routing_path_label(task_spec)
    return label, task_spec
