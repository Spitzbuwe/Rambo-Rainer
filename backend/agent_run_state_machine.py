"""Agent Run State Machine — Level 8.1.

Formal state machine for agent run lifecycle.
Enforces valid stage transitions; rejects invalid ones with a clear error.
"""
from __future__ import annotations

from typing import FrozenSet, Tuple

# Ordered canonical states
VALID_STATES: Tuple[str, ...] = (
    "planned",
    "context_loaded",
    "patch_ready",
    "validated",
    "test_ready",
    "apply_ready",
    "applied",
    "tested",
    "done",
    "blocked",
    "failed",
)

VALID_STATES_SET: FrozenSet[str] = frozenset(VALID_STATES)

# Which states each state may transition TO
VALID_TRANSITIONS: dict[str, FrozenSet[str]] = {
    "planned":        frozenset({"context_loaded", "blocked", "failed"}),
    "context_loaded": frozenset({"patch_ready", "blocked", "failed"}),
    "patch_ready":    frozenset({"validated", "blocked", "failed"}),
    "validated":      frozenset({"test_ready", "apply_ready", "blocked", "failed"}),
    "test_ready":     frozenset({"apply_ready", "blocked", "failed"}),
    "apply_ready":    frozenset({"applied", "blocked"}),
    "applied":        frozenset({"tested", "failed"}),
    "tested":         frozenset({"done", "failed"}),
    "done":           frozenset(),
    "blocked":        frozenset({"planned"}),
    "failed":         frozenset({"planned"}),
}

# Terminal states — no further transitions possible (except retry reset to planned)
TERMINAL_STATES: FrozenSet[str] = frozenset({"done"})

# States that allow a write-gate token to be acquired
WRITE_ELIGIBLE_STATES: FrozenSet[str] = frozenset({"apply_ready"})


def is_valid_state(state: str) -> bool:
    return str(state) in VALID_STATES_SET


def can_transition(from_state: str, to_state: str) -> Tuple[bool, str]:
    """Return (allowed, message)."""
    if from_state not in VALID_STATES_SET:
        return False, f"Ungültiger Ausgangszustand: {from_state!r}"
    if to_state not in VALID_STATES_SET:
        return False, f"Ungültiger Zielzustand: {to_state!r}"
    if to_state in VALID_TRANSITIONS[from_state]:
        return True, ""
    return (
        False,
        f"Übergang {from_state!r} → {to_state!r} nicht erlaubt. "
        f"Erlaubt: {sorted(VALID_TRANSITIONS[from_state]) or 'keine'}",
    )


class AgentRunStateMachine:
    """
    Tracks and enforces state transitions for a single agent run.

    Usage:
        sm = AgentRunStateMachine(run_id="ar_abc123")
        sm.transition("context_loaded")   # planned → context_loaded
        sm.transition("patch_ready")      # context_loaded → patch_ready
        sm.history                        # ["planned", "context_loaded", "patch_ready"]
    """

    def __init__(self, run_id: str, initial_state: str = "planned") -> None:
        if initial_state not in VALID_STATES_SET:
            raise ValueError(f"Ungültiger Ausgangszustand: {initial_state!r}")
        self.run_id = str(run_id)
        self._state = str(initial_state)
        self._history: list[str] = [self._state]

    @property
    def state(self) -> str:
        return self._state

    @property
    def history(self) -> list[str]:
        return list(self._history)

    def transition(self, to_state: str) -> Tuple[bool, str]:
        """Attempt a transition. Returns (success, message)."""
        allowed, msg = can_transition(self._state, to_state)
        if allowed:
            self._state = to_state
            self._history.append(to_state)
            return True, ""
        return False, msg

    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    def can_write(self) -> bool:
        return self._state in WRITE_ELIGIBLE_STATES

    def reset_to_planned(self) -> bool:
        """Reset from blocked/failed back to planned."""
        if self._state in ("blocked", "failed"):
            self._state = "planned"
            self._history.append("planned")
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "state": self._state,
            "history": self._history,
            "is_terminal": self.is_terminal(),
            "can_write": self.can_write(),
        }


__all__ = [
    "VALID_STATES",
    "VALID_STATES_SET",
    "VALID_TRANSITIONS",
    "TERMINAL_STATES",
    "WRITE_ELIGIBLE_STATES",
    "is_valid_state",
    "can_transition",
    "AgentRunStateMachine",
]
