# -*- coding: utf-8 -*-
"""Chat-Fallback bei Offline-/Verbindungsfragen (kein generisches „Ich bin bereit…“)."""

from __future__ import annotations

import main as m


def test_connectivity_fallback_for_ueberpruefe_offline():
    fb = m._connectivity_chat_fallback("überprüfe warum die app offline ist")
    assert "Backend" in fb
    assert "127.0.0.1" in fb


def test_connectivity_fallback_irrelevant_prompt_empty():
    assert m._connectivity_chat_fallback("erklär mir Python") == ""


def test_effective_chat_timeout_extended_for_connectivity():
    assert m._effective_chat_timeout_sec("überprüfe warum die app offline ist", None) >= m._CONNECTIVITY_CHAT_TIMEOUT_SEC - 1
