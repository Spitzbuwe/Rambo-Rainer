# -*- coding: utf-8 -*-
"""Tests für POST /api/scaffold."""

from __future__ import annotations

import requests


def test_scaffold_web_app(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "web_app", "app_name": "my_dashboard", "features": []},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["app_type"] == "web_app"
    assert data["app_name"] == "my_dashboard"
    assert len(data["files"]) > 0
    assert "first_steps" in data
    assert all("code" in f for f in data["files"])


def test_scaffold_tool(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "tool", "app_name": "my_tool"},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["app_type"] == "tool"
    assert len(data["files"]) >= 1


def test_scaffold_dashboard(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "dashboard", "app_name": "live_monitor"},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    blob = str(data).lower()
    assert "websocket" in blob or "files" in data


def test_scaffold_with_features(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "web_app", "app_name": "real_time_app", "features": ["websocket", "docker"]},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    assert "additional_setup" in data or "docker_compose" in data


def test_scaffold_dashboard_features_websocket_docker(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "dashboard", "app_name": "live_stats", "features": ["websocket", "docker"]},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    assert "additional_setup" in data
    assert data.get("docker_compose") is False


def test_scaffold_invalid_type(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "invalid_type", "app_name": "test"},
        timeout=15,
    )
    assert r.status_code == 400
    assert "unbekannt" in r.json().get("error", "").lower()


def test_scaffold_structure(base_url):
    r = requests.post(
        f"{base_url}/api/scaffold",
        json={"app_type": "web_app", "app_name": "structured_app"},
        timeout=15,
    )
    assert r.status_code == 200
    data = r.json()
    for key in ("app_name", "app_type", "directories", "files", "first_steps"):
        assert key in data, f"Fehlender Key: {key}"
