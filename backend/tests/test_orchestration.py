# -*- coding: utf-8 -*-
"""Tests für POST /api/build-full."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from server import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "data" / "state.json"


@pytest.fixture
def client():
    with app.test_client() as c:
        yield c


@pytest.fixture
def temp_dir():
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def state_backup():
    backup = None
    if STATE_PATH.is_file():
        backup = STATE_PATH.read_text(encoding="utf-8")
    yield
    if backup is not None:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(backup, encoding="utf-8")
    elif STATE_PATH.is_file():
        try:
            STATE_PATH.unlink()
        except OSError:
            pass


def test_build_full_web_app(client, temp_dir, state_backup):
    response = client.post(
        "/api/build-full",
        json={
            "app_type": "web_app",
            "app_name": "demo_app",
            "features": [],
            "base_path": temp_dir,
        },
    )
    assert response.status_code in (200, 207)
    data = response.get_json()
    assert "orchestration_id" in data
    assert "stages" in data
    assert "summary" in data


def test_build_full_tool(client, temp_dir, state_backup):
    response = client.post(
        "/api/build-full",
        json={
            "app_type": "tool",
            "app_name": "my_tool",
            "base_path": temp_dir,
        },
    )
    assert response.status_code in (200, 207)
    data = response.get_json()
    assert data["summary"]["files_written"] > 0


def test_build_full_stages(client, temp_dir, state_backup):
    response = client.post(
        "/api/build-full",
        json={
            "app_type": "web_app",
            "app_name": "full_test",
            "base_path": temp_dir,
        },
    )
    assert response.status_code in (200, 207)
    data = response.get_json()
    stages = data["stages"]
    assert "stage_1_coach" in stages
    assert "stage_2_scaffold" in stages
    assert "stage_3_generate" in stages
    assert "stage_4_dev_workflow" in stages
    assert "stage_5_final_coach" in stages


def test_build_full_files_created(client, temp_dir, state_backup):
    response = client.post(
        "/api/build-full",
        json={
            "app_type": "web_app",
            "app_name": "filetest",
            "base_path": temp_dir,
        },
    )
    assert response.status_code in (200, 207)
    data = response.get_json()
    assert data["summary"]["files_written"] > 0


def test_build_full_state_updated(client, temp_dir, state_backup):
    response = client.post(
        "/api/build-full",
        json={
            "app_type": "web_app",
            "app_name": "state_full_test",
            "base_path": temp_dir,
        },
    )
    assert response.status_code in (200, 207)

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert "orchestrations" in state
    assert len(state["orchestrations"]) > 0
