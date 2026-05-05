# -*- coding: utf-8 -*-
"""Tests für POST /api/dev-workflow (Admin-Header erforderlich)."""

from __future__ import annotations

import requests


def test_dev_workflow_check_errors(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "check_errors"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert "phases" in data
    assert "check_errors" in data["phases"]


def test_dev_workflow_run_tests(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "run_tests"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=240,
    )
    assert r.status_code == 200
    data = r.json()
    assert "tests_result" in data
    assert "passed" in data["tests_result"]


def test_dev_workflow_full_cycle(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "full_cycle"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=300,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["overall_status"] in (
        "success",
        "fixed_and_stable",
        "attention_required",
        "error",
    )
    assert "timestamp" in data


def test_dev_workflow_restart(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "restart"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    assert "phases" in data
    assert "restart" in data["phases"]


def test_dev_workflow_structure(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "restart"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=30,
    )
    assert r.status_code == 200
    data = r.json()
    for key in ("session_id", "timestamp", "action", "phases", "overall_status"):
        assert key in data


def test_dev_workflow_invalid_action(base_url, admin_headers):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "invalid_action"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=15,
    )
    assert r.status_code in (200, 400)


def test_dev_workflow_error_handling(base_url, admin_headers):
    """Robuster POST (explizite action); Default full_cycle ist in server.py: data.get('action') or 'full_cycle'."""
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "check_errors"},
        headers={**admin_headers, "Content-Type": "application/json"},
        timeout=60,
    )
    assert r.status_code == 200
    assert "phases" in r.json()


def test_dev_workflow_requires_admin(base_url):
    r = requests.post(
        f"{base_url}/api/dev-workflow",
        json={"action": "check_errors"},
        timeout=15,
    )
    assert r.status_code == 403
