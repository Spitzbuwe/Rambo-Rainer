# -*- coding: utf-8 -*-
"""Tests für POST /api/generate/write-files."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

import server

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "data" / "state.json"


@pytest.fixture
def client():
    with server.app.test_client() as c:
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


def test_write_single_file(client, temp_dir):
    response = client.post(
        "/api/generate/write-files",
        json={
            "app_name": "test_app",
            "app_type": "web_app",
            "files": [{"path": "src/main.py", "code": 'print("Hello World")'}],
            "base_path": temp_dir,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["written_files"]) == 1
    assert data["summary"]["successfully_written"] == 1


def test_write_multiple_files(client, temp_dir):
    response = client.post(
        "/api/generate/write-files",
        json={
            "app_name": "multi_app",
            "app_type": "web_app",
            "files": [
                {"path": "src/app.py", "code": "from flask import Flask"},
                {"path": "src/config.py", "code": "DEBUG = True"},
                {"path": "frontend/App.jsx", "code": "export default function App() {}"},
            ],
            "base_path": temp_dir,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["written_files"]) == 3


def test_write_creates_directories(client, temp_dir):
    response = client.post(
        "/api/generate/write-files",
        json={
            "app_name": "dir_test",
            "app_type": "web_app",
            "files": [{"path": "deeply/nested/dir/file.py", "code": "x = 1"}],
            "base_path": temp_dir,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    full_path = os.path.join(temp_dir, "deeply", "nested", "dir", "file.py")
    assert os.path.exists(full_path)


def test_write_utf8_encoding(client, temp_dir):
    response = client.post(
        "/api/generate/write-files",
        json={
            "app_name": "utf8_test",
            "app_type": "tool",
            "files": [
                {
                    "path": "test_ümläuts.py",
                    "code": "# Äußerst wichtig: Überprüfung läuft",
                }
            ],
            "base_path": temp_dir,
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"


def test_write_updates_state(client, temp_dir, state_backup):
    if STATE_PATH.is_file():
        STATE_PATH.unlink()

    response = client.post(
        "/api/generate/write-files",
        json={
            "app_name": "state_test",
            "app_type": "web_app",
            "files": [{"path": "test.py", "code": "test"}],
            "base_path": temp_dir,
        },
    )
    assert response.status_code == 200

    assert STATE_PATH.is_file()
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert state.get("files_created") is True
    assert "last_generation" in state
