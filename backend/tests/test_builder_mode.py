# -*- coding: utf-8 -*-
"""Tests für POST /api/builder-mode."""

from __future__ import annotations

import pytest
import requests


def test_builder_mode_intent_detected(base_url):
    r = requests.post(
        f"{base_url}/api/builder-mode",
        json={"input": "Bau mir eine App zur Aufgabenverwaltung"},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("builder_mode_active") is True
    assert body.get("intent_recognized") is True
    assert "capability" in body
    assert isinstance(body.get("dev_workflow"), list)
    assert body.get("message", "").startswith("✅")


def test_builder_mode_no_intent(base_url):
    r = requests.post(
        f"{base_url}/api/builder-mode",
        json={"input": "Wie funktionieren deine Rules?"},
        timeout=10,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("builder_mode_active") is False
    assert body.get("intent_recognized") is False


@pytest.mark.parametrize(
    "text",
    [
        "Programmiere mir ein Dashboard",
        "Erstelle mir eine App",
        "Kannst du mir ein Tool entwickeln?",
        "Mach mir ein Monitoring-Tool",
        "Bau mir einen KI-Agent",
    ],
)
def test_builder_mode_trigger_variants(base_url, text):
    r = requests.post(f"{base_url}/api/builder-mode", json={"input": text}, timeout=10)
    assert r.status_code == 200
    assert r.json().get("builder_mode_active") is True
