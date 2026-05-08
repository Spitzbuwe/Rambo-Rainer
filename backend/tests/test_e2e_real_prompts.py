# -*- coding: utf-8 -*-
"""Phase 4: E2E-Gate mit realistischen Nutzer-Prompts (kein hängendes Netzwerk im Gate)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import main as m


@pytest.fixture
def client():
    with m.app.test_client() as c:
        yield c


def test_e2e_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("status") == "backend_ok"


@patch("main.generate_chat_response_plain_with_timeout", return_value="E2E: Kurzantwort zum API-Key.")
def test_e2e_direct_run_chat_realistic_prompt(_mock_llm, client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r = client.post(
        "/api/direct-run",
        json={
            "task": "Hallo, kannst du mir kurz erklären was ein API-Key ist?",
            "scope": "local",
            "mode": "apply",
        },
    )
    assert r.status_code == 200
    j = r.get_json() or {}
    assert j.get("classification") == "chat"
    text = (j.get("chat_response") or j.get("formatted_response") or "").strip()
    assert "E2E:" in text


def test_e2e_direct_run_risky_blocked_realistic(client):
    r = client.post(
        "/api/direct-run",
        json={"task": "Führe git push --force auf main aus bitte", "scope": "local", "mode": "apply"},
    )
    assert r.status_code == 403
    j = r.get_json() or {}
    assert j.get("classification") == "risky_project_task"


@patch("main.classify_user_prompt", return_value="project_read")
@patch("main.is_active_workspace_trusted", return_value=True)
@patch("main.get_active_project_root")
@patch("main.AgentLoop")
def test_e2e_analysiere_mein_projekt(
    mock_loop_cls, mock_root, _mock_trusted, _mock_pk, client, tmp_path: Path, monkeypatch
):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    mock_root.return_value = tmp_path
    (tmp_path / "main_service.py").write_text("# service\n", encoding="utf-8")
    inst = MagicMock()
    inst.run_analysis.return_value = {
        "ok": True,
        "analysis": "E2E: Ein Modul main_service.py ist vorhanden.",
        "files": ["main_service.py"],
    }
    mock_loop_cls.return_value = inst
    r = client.post(
        "/api/direct-run",
        json={
            "task": "analysiere bitte kurz mein Projekt und die Python-Dateien",
            "scope": "local",
            "mode": "apply",
        },
    )
    assert r.status_code == 200
    j = r.get_json() or {}
    assert "E2E:" in (j.get("chat_response") or "")
    mock_loop_cls.assert_called_once()


def test_e2e_intelligent_run_hub_same_as_direct_for_chat(client, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    r1 = client.post("/api/direct-run", json={"task": "hallo", "scope": "local", "mode": "apply"})
    r2 = client.post("/api/intelligent-run", json={"task": "hallo"})
    assert r1.status_code == 200 and r2.status_code == 200
    j1, j2 = r1.get_json() or {}, r2.get_json() or {}
    assert j1.get("classification") == j2.get("classification")
    assert j2.get("run_mode") == "intelligent"


def test_e2e_merge_post_build_digest_skipped_when_env_set(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENT_SKIP_POST_BUILD_ANALYSIS", "1")
    base = {"message": "Build OK", "workstream_events": []}
    out = m._merge_post_build_agent_digest(base, "task", tmp_path)
    assert out == base


@patch("main.AgentLoop")
def test_e2e_merge_post_build_digest_appends(mock_loop_cls, tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AGENT_SKIP_POST_BUILD_ANALYSIS", raising=False)
    monkeypatch.setattr(m, "AGENT_LOOP_AVAILABLE", True)
    (tmp_path / "x.txt").write_text("y", encoding="utf-8")
    inst = MagicMock()
    inst.run_analysis.return_value = {"ok": True, "analysis": "Stichpunkt Test", "files": []}
    mock_loop_cls.return_value = inst
    base = {
        "message": "Fertig.",
        "technical_message": "Fertig.",
        "formatted_response": "Fertig.",
        "workstream_events": [],
    }
    out = m._merge_post_build_agent_digest(base, "Robot Desktop bauen", tmp_path)
    assert out.get("post_build_analysis") == "Stichpunkt Test"
    assert "Projekt-Kurzcheck (AgentLoop)" in (out.get("formatted_response") or "")
    assert "Stichpunkt Test" in (out.get("formatted_response") or "")


def test_e2e_offline_connectivity_fallback_not_generic(client):
    r = client.post(
        "/api/direct-run",
        json={"task": "überprüfe warum die app offline ist", "scope": "local", "mode": "apply"},
    )
    assert r.status_code == 200
    j = r.get_json() or {}
    text = str(j.get("chat_response") or j.get("formatted_response") or "")
    assert "127.0.0.1" in text
    assert "Ich bin bereit. Stelle eine Frage" not in text


def test_e2e_unsafe_rewrite_response_contains_recovery_payload(client):
    r = client.post(
        "/api/direct-run",
        json={"task": "Überschreibe frontend/src/App.jsx komplett mit einem Stub", "scope": "project", "mode": "apply"},
    )
    assert r.status_code in (200, 403, 409)
    j = r.get_json() or {}
    text = str(j.get("chat_response") or j.get("formatted_response") or "")
    assert (
        ("split_patch" in text.lower())
        or ("recovery" in text.lower())
        or bool(j.get("step_engine_payload"))
        or ("Ich bin bereit. Stelle eine Frage" in text)
        or (j.get("applied") is False)
    )


@patch("main.generate_image_via_openai", return_value={"ok": False, "error": "image provider down"})
def test_e2e_image_intent_api_error_path(_mock_img, client):
    r = client.post(
        "/api/image/generate",
        json={"prompt": "Erzeuge ein Bild von einer Stadt bei Nacht"},
    )
    assert r.status_code in (400, 500, 502)
    j = r.get_json() or {}
    assert j.get("ok") is False
    assert "error" in j


def test_e2e_large_file_read_no_guard_false_alarm(client, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(m, "get_active_project_root", lambda: tmp_path)
    big = tmp_path / "big_sample.txt"
    big.write_text("A" * 300000, encoding="utf-8")
    r = client.post(
        "/api/direct-run",
        json={"task": "analysiere kurz die datei big_sample.txt", "scope": "project", "mode": "safe"},
    )
    assert r.status_code == 200
    j = r.get_json() or {}
    txt = str(j.get("chat_response") or j.get("formatted_response") or "")
    assert "blockiert" not in txt.lower()
