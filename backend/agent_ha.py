"""
HA Stub
Auto-generiertes Rainer-Agent-Mega-Modul — API stabil, Logik schrittweise erweiterbar.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class HighAvailabilityStub:
    """HA Stub"""

    __slots__ = ("project_root",)

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def health(self) -> dict[str, Any]:
        return {"module": "agent_ha", "class": "HighAvailabilityStub", "ok": True}

    def describe(self) -> str:
        return "HA Stub"


def get_instance(project_root: Path | str | None = None) -> HighAvailabilityStub:
    return HighAvailabilityStub(project_root)


__all__ = ["HighAvailabilityStub", "get_instance"]
