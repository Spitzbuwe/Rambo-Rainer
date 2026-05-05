"""Smoke-Tests fuer Mega-Agent-Module (Import + health + /api/agent/mega/status)."""

from __future__ import annotations

import importlib

import pytest

from main_agent_integration import MEGA_MODULE_NAMES


@pytest.mark.parametrize("mod_name", MEGA_MODULE_NAMES)
def test_mega_module_importable(mod_name: str) -> None:
    importlib.import_module(mod_name)


def _health_for_module(mod):
    if hasattr(mod, "get_instance"):
        return mod.get_instance().health()
    if hasattr(mod, "multi_llm_router"):
        return mod.multi_llm_router.health()
    if hasattr(mod, "continual_learning"):
        return mod.continual_learning.health()
    if hasattr(mod, "advanced_reasoning"):
        return mod.advanced_reasoning.health()
    raise AssertionError("kein health-Einstieg")


@pytest.mark.parametrize("mod_name", MEGA_MODULE_NAMES)
def test_mega_module_health(mod_name: str) -> None:
    mod = importlib.import_module(mod_name)
    h = _health_for_module(mod)
    assert isinstance(h, dict)
    assert h.get("ok") is True


def test_mega_http_status():
    import main as m

    c = m.app.test_client()
    r = c.get("/api/agent/mega/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert int(data.get("importable_count") or 0) >= len(MEGA_MODULE_NAMES) - 2
