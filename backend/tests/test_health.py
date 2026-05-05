# -*- coding: utf-8 -*-
"""Erweiterter Health-Check (Phase 20)."""

from __future__ import annotations

import pytest
import requests

pytestmark = [pytest.mark.smoke, pytest.mark.integration]


def test_health_200(base_url):
    resp = requests.get(f"{base_url}/api/health", timeout=10)
    assert resp.status_code == 200


def test_health_body_schema(base_url):
    resp = requests.get(f"{base_url}/api/health", timeout=10)
    body = resp.json()
    assert body.get("status") == "healthy"
    assert "db" in body
    assert body.get("db") in ("ok", "fallback_state_json", "error")
    assert body.get("timestamp")
