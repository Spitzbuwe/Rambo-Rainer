# -*- coding: utf-8 -*-
"""Phase 22: Socket.IO-Grundgerüst für Live-Updates (Admins / Agents)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from flask import request
from flask_socketio import SocketIO, join_room, leave_room

ROOM_ADMINS = "admins"
ROOM_AGENTS = "agents"

_socketio: Optional[SocketIO] = None
_admin_token: str = ""


def get_socketio() -> Optional[SocketIO]:
    return _socketio


def emit_to_admins(event: str, data: Dict[str, Any]) -> None:
    """Sendet ein Event an alle Clients in Raum ``admins``."""
    if _socketio:
        _socketio.emit(event, data, room=ROOM_ADMINS)


def emit_to_agents(event: str, data: Dict[str, Any]) -> None:
    """Sendet ein Event an alle Clients in Raum ``agents``."""
    if _socketio:
        _socketio.emit(event, data, room=ROOM_AGENTS)


def emit_db_health_to_admins(payload: Dict[str, Any]) -> None:
    """Kurzform: DB-Status an Admins (Server-seitig nutzbar)."""
    emit_to_admins("db_health_check", payload)


def _token_ok(provided: Optional[str]) -> bool:
    e = str(_admin_token or "").strip()
    g = str(provided or "").strip()
    return bool(e and g == e)


def init_socketio_app(app, admin_token: str, cors_origins: str = "*") -> SocketIO:
    """Registriert Socket.IO am Flask-App-Objekt und verbindet Event-Handler."""
    global _socketio, _admin_token
    _admin_token = str(admin_token or "").strip()
    _socketio = SocketIO(app, cors_allowed_origins=cors_origins, async_mode="threading")

    @_socketio.on("connect")
    def on_connect():
        """Handshake: nur mit gültigem ``?admin_token=…`` (Query) erlaubt."""
        tok = request.args.get("admin_token")
        if not tok:
            return False
        if not _token_ok(tok):
            return False
        join_room(ROOM_ADMINS)
        prefix = str(tok)[:10]
        print(f"[WebSocket] Admin connected (token prefix: {prefix}…)")
        _socketio.emit("admin_connected", {"ok": True})
        return True

    @_socketio.on("disconnect")
    def on_disconnect():
        leave_room(ROOM_ADMINS)
        leave_room(ROOM_AGENTS)

    @_socketio.on("admin_connect")
    def on_admin_connect(data):
        """Legacy: nach erfolgreichem ``connect`` optional; Token nur falls mitgeschickt."""
        if isinstance(data, dict) and data.get("token") is not None and not _token_ok(
            data.get("token")
        ):
            return
        join_room(ROOM_ADMINS)
        _socketio.emit("admin_connected", {"ok": True})

    @_socketio.on("admin_disconnect")
    def on_admin_disconnect():
        leave_room(ROOM_ADMINS)

    @_socketio.on("agent_connect")
    def on_agent_connect(data):
        if not isinstance(data, dict):
            return
        aid = str(data.get("agent_id") or data.get("uuid") or "").strip()
        if not aid:
            return
        join_room(ROOM_AGENTS)
        _socketio.emit(
            "agent_connected",
            {"agent_id": aid, "status": "online"},
            room=ROOM_AGENTS,
        )

    @_socketio.on("rule_updated")
    def on_rule_updated_client(data):
        """Optional: Client meldet Änderung → an Admins weiterreichen."""
        if not isinstance(data, dict):
            return
        emit_to_admins("rule_updated", data)

    @_socketio.on("db_health_check")
    def on_db_health_client(data):
        """Optional: Client/Middleware triggert Broadcast des DB-Status."""
        if not isinstance(data, dict):
            return
        emit_to_admins("db_health_check", data)

    return _socketio
