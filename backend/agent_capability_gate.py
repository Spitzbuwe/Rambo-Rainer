"""Agent Capability Gate — Level 8.8.

Each agent role has fixed capabilities.
No agent may perform an action it is not permitted to do.
"""
from __future__ import annotations

from typing import Tuple

# Role → capability → bool
_CAPS: dict[str, dict[str, bool]] = {
    "planner": {
        "can_read": False,
        "can_write": False,
        "can_plan": True,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": False,
    },
    "memory": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": True,
    },
    "context": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": False,
    },
    "patch": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": True,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": False,
    },
    "apply": {
        "can_read": True,
        "can_write": True,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": True,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": False,
    },
    "safety": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": True,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": True,
        "can_search_memory": False,
    },
    "test": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": True,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": False,
        "can_search_memory": False,
    },
    "review": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": False,
        "can_review": True,
        "can_search_memory": False,
    },
    "commit": {
        "can_read": True,
        "can_write": False,
        "can_plan": False,
        "can_create_patch": False,
        "can_apply_patch": False,
        "can_run_checks": False,
        "can_run_shell": False,
        "can_commit": False,
        "can_prepare_commit": True,
        "can_review": False,
        "can_search_memory": False,
    },
}

# Agents that may only read (never write)
READ_ONLY_ROLES: frozenset[str] = frozenset(
    role for role, caps in _CAPS.items() if not caps.get("can_write")
)

# Agents that require a write-gate token
WRITE_ROLES: frozenset[str] = frozenset(
    role for role, caps in _CAPS.items() if caps.get("can_write")
)


def check_capability(agent_role: str, capability: str) -> Tuple[bool, str]:
    """Return (allowed, message). Message is empty when allowed."""
    caps = _CAPS.get(agent_role)
    if caps is None:
        return False, f"Unbekannte Agent-Rolle: {agent_role!r}"
    if capability not in caps:
        return False, f"Unbekannte Capability: {capability!r}"
    if not caps[capability]:
        return False, f"{agent_role.capitalize()}Agent: {capability!r} nicht erlaubt"
    return True, ""


def get_capabilities(agent_role: str) -> dict[str, bool]:
    """Return a copy of the capability dict for the given role."""
    return dict(_CAPS.get(agent_role, {}))


def list_agent_roles() -> list[str]:
    return list(_CAPS.keys())


def is_read_only(agent_role: str) -> bool:
    return agent_role in READ_ONLY_ROLES


__all__ = [
    "check_capability",
    "get_capabilities",
    "list_agent_roles",
    "is_read_only",
    "READ_ONLY_ROLES",
    "WRITE_ROLES",
]
