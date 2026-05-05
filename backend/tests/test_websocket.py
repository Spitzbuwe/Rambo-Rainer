# -*- coding: utf-8 -*-
"""Tests für Phase-22-Socket.IO-Grundgerüst (emit, Init, Anbindung an Rule-Create)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import websocket as ws


def test_emit_to_admins_noop_when_socketio_unconfigured():
    prev = ws._socketio
    ws._socketio = None
    try:
        ws.emit_to_admins("rule_updated", {"x": 1})
    finally:
        ws._socketio = prev


def test_emit_to_admins_forwards_to_room():
    prev = ws._socketio
    mock_sio = MagicMock()
    ws._socketio = mock_sio
    try:
        ws.emit_to_admins("rule_updated", {"fingerprint": "abc", "status": "created"})
        mock_sio.emit.assert_called_once_with(
            "rule_updated", {"fingerprint": "abc", "status": "created"}, room=ws.ROOM_ADMINS
        )
    finally:
        ws._socketio = prev


def test_emit_to_agents_forwards_to_room():
    prev = ws._socketio
    mock_sio = MagicMock()
    ws._socketio = mock_sio
    try:
        ws.emit_to_agents("ping", {"agent_id": "a1"})
        mock_sio.emit.assert_called_once_with("ping", {"agent_id": "a1"}, room=ws.ROOM_AGENTS)
    finally:
        ws._socketio = prev


def test_init_socketio_app_registers_instance():
    prev_sio = ws._socketio
    prev_tok = ws._admin_token
    from flask import Flask

    app = Flask(__name__)
    try:
        sio = ws.init_socketio_app(app, admin_token="secret-test-token")
        assert sio is not None
        assert ws.get_socketio() is sio
    finally:
        ws._socketio = prev_sio
        ws._admin_token = prev_tok


def test_socket_connect_accepts_query_admin_token():
    from flask import Flask

    prev_sio = ws._socketio
    prev_tok = ws._admin_token
    app = Flask(__name__)
    try:
        sio = ws.init_socketio_app(app, admin_token="good-token")
        client = sio.test_client(app)
        client.connect(query_string="admin_token=good-token")
        assert client.is_connected() is True
        client.disconnect()
    finally:
        ws._socketio = prev_sio
        ws._admin_token = prev_tok


def test_socket_connect_rejects_wrong_token():
    from flask import Flask

    prev_sio = ws._socketio
    prev_tok = ws._admin_token
    app = Flask(__name__)
    try:
        sio = ws.init_socketio_app(app, admin_token="good-token")
        client = sio.test_client(app)
        client.connect(query_string="admin_token=bad")
        assert client.is_connected() is False
    finally:
        ws._socketio = prev_sio
        ws._admin_token = prev_tok


def test_socket_connect_rejects_missing_token():
    from flask import Flask

    prev_sio = ws._socketio
    prev_tok = ws._admin_token
    app = Flask(__name__)
    try:
        sio = ws.init_socketio_app(app, admin_token="good-token")
        client = sio.test_client(app)
        client.connect()
        assert client.is_connected() is False
    finally:
        ws._socketio = prev_sio
        ws._admin_token = prev_tok


def test_api_rules_create_triggers_emit(monkeypatch, admin_headers):
    calls = []

    def capture(ev, data):
        calls.append((ev, data))

    monkeypatch.setattr(ws, "emit_to_admins", capture)
    import server

    with server.app.test_client() as client:
        resp = client.post(
            "/api/rules/create",
            json={"name": "ws-pytest-rule", "description": "socket test"},
            headers=admin_headers,
        )
    assert resp.status_code == 200
    assert resp.get_json().get("success") is True
    assert any(ev == "rule_updated" and data.get("status") == "created" for ev, data in calls)
