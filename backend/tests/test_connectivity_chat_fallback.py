# -*- coding: utf-8 -*-
"""Chat-Fallback bei Offline-/Verbindungsfragen (kein generisches „Ich bin bereit…“)."""

from __future__ import annotations

from unittest.mock import patch

import agent_api
import main as m
from prompt_routing import chat_reply_canned, connectivity_diagnostics_reply


def test_chat_reply_canned_connectivity_not_generic():
    text = chat_reply_canned("überprüfe warum die app offline ist")
    assert text == connectivity_diagnostics_reply()
    assert "Ich bin bereit. Stelle eine Frage" not in text


def test_connectivity_fallback_for_ueberpruefe_offline():
    fb = m._connectivity_chat_fallback("überprüfe warum die app offline ist")
    assert "Backend" in fb
    assert "127.0.0.1" in fb


def test_connectivity_fallback_irrelevant_prompt_empty():
    assert m._connectivity_chat_fallback("erklär mir Python") == ""


def test_effective_chat_timeout_extended_for_connectivity():
    assert m._effective_chat_timeout_sec("überprüfe warum die app offline ist", None) >= m._CONNECTIVITY_CHAT_TIMEOUT_SEC - 1


def test_agent_formatting_preserves_llm_failure_not_canned():
    err = (
        "⚠️ Lokaler Provider [ollama] **Ollama** (Modell: m) nicht erreichbar oder Antwort ungueltig: x\n\n"
        "Hinweis: Ollama starten"
    )
    with patch.object(agent_api, "generate_chat_response", return_value=err):
        assert agent_api._formatting_chat_reply("hallo") == err
        assert "Ich bin bereit. Stelle eine Frage" not in err


def test_agent_formatting_empty_connectivity_checklist():
    with patch.object(agent_api, "generate_chat_response", return_value=""):
        out = agent_api._formatting_chat_reply("überprüfe warum die app offline ist")
        assert "127.0.0.1" in out
        assert "Ich bin bereit. Stelle eine Frage" not in out


@patch("main.generate_chat_response_plain_with_timeout", return_value="Ich bin bereit. Stelle eine Frage.")
@patch("main.classify_user_prompt", return_value="unknown")
def test_direct_run_unknown_project_prompt_avoids_generic_ready(_m_pk, _m_llm):
    with m.app.test_client() as c:
        r = c.post(
            "/api/direct-run",
            json={"task": "ändere bitte app.jsx und verbessere den header", "scope": "project", "mode": "apply"},
        )
    assert r.status_code == 200
    body = r.get_json() or {}
    text = str(body.get("chat_response") or body.get("formatted_response") or "")
    assert "Ich bin bereit. Stelle eine Frage" not in text
