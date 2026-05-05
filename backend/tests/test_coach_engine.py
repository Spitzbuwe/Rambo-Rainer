# -*- coding: utf-8 -*-
"""Tests für POST /api/coach/next-step."""

from __future__ import annotations

import pytest

import server


@pytest.fixture
def client():
    with server.app.test_client() as c:
        yield c


def test_coach_next_step_empty_state(client):
    """Coach schlägt Scaffold vor wenn State ohne Fortschritt."""
    response = client.post("/api/coach/next-step", json={})
    assert response.status_code == 200
    data = response.get_json()
    assert data is not None
    assert "next_step" in data
    assert "current_state" in data
    assert "recommendation" in data


def test_coach_detects_risks(client):
    response = client.post("/api/coach/next-step", json={})
    assert response.status_code == 200
    data = response.get_json()
    assert "detected_risks" in data


def test_coach_response_structure(client):
    response = client.post("/api/coach/next-step", json={})
    assert response.status_code == 200
    data = response.get_json()
    required = ["next_step", "current_state", "detected_risks", "recommendation", "template_response"]
    for key in required:
        assert key in data


def test_coach_with_context(client):
    response = client.post(
        "/api/coach/next-step",
        json={"context": "User hat Feature X angefordert"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["next_step"] is not None
