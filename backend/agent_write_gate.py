"""Agent Write Gate — Level 8.7.

Central gate that ensures only one agent writes at a time.
Prevents race conditions and conflicting patches in multi-agent runs.
"""
from __future__ import annotations

import threading
from typing import Optional, Tuple
from uuid import uuid4


class AgentWriteGate:
    """
    Singleton write gate.
    - acquire_write_token()  → one token per run_id
    - validate_and_consume() → token is single-use
    - Blocked when another run holds the gate
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_token: Optional[str] = None
        self._current_run_id: Optional[str] = None
        self._used_tokens: set[str] = set()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def acquire_write_token(self, run_id: str) -> Tuple[str, bool, str]:
        """
        Try to acquire a write token.
        Returns (token, success, message).
        Token is empty string on failure.
        """
        with self._lock:
            if self._current_token is not None:
                return (
                    "",
                    False,
                    f"Write-Gate belegt: laufender Run {self._current_run_id!r}",
                )
            token = str(uuid4())
            self._current_token = token
            self._current_run_id = str(run_id)
            return token, True, "ok"

    def validate_and_consume(self, token: str, run_id: str) -> Tuple[bool, str]:
        """
        Validate a write token and consume it (single-use).
        Returns (valid, message).
        """
        with self._lock:
            if not token:
                return False, "Kein Token angegeben"
            if token in self._used_tokens:
                return False, "Token bereits verwendet"
            if self._current_token != token:
                return False, "Token ungültig oder abgelaufen"
            if self._current_run_id != str(run_id):
                return False, "Token gehört zu anderem Run"
            self._used_tokens.add(token)
            self._current_token = None
            self._current_run_id = None
            return True, "ok"

    def release(self, token: str) -> None:
        """Release the gate without consuming (e.g. on error)."""
        with self._lock:
            if self._current_token == token:
                self._current_token = None
                self._current_run_id = None

    @property
    def is_busy(self) -> bool:
        with self._lock:
            return self._current_token is not None

    @property
    def current_run_id(self) -> Optional[str]:
        with self._lock:
            return self._current_run_id

    def reset(self) -> None:
        """For testing only."""
        with self._lock:
            self._current_token = None
            self._current_run_id = None
            self._used_tokens.clear()


# -- Singleton --
_instance: Optional[AgentWriteGate] = None
_instance_lock = threading.Lock()


def get_instance() -> AgentWriteGate:
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = AgentWriteGate()
    return _instance


__all__ = ["AgentWriteGate", "get_instance"]
