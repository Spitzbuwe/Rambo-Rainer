"""Phase 1: Risky zuerst, Groq-Mock, kein zweites Groq im classify_user_prompt-Fallback."""
from __future__ import annotations

from unittest.mock import patch

from backend.prompt_routing import (
    _is_risky_user_intent,
    classify_user_prompt,
    classify_with_groq,
    should_route_direct_run_as_chat,
)


def test_is_risky_detects_git_push():
    assert _is_risky_user_intent("Bitte git push auf main") is True


def test_is_risky_false_for_normal_edit():
    assert _is_risky_user_intent("Ändere in frontend/src/App.jsx die Überschrift") is False


def test_classify_user_prompt_risky_without_groq(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert classify_user_prompt("git merge feature-x") == "risky_project_task"


@patch("backend.prompt_routing.requests.post")
def test_classify_with_groq_parses_chat(mock_post, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "chat"}}],
    }
    assert classify_with_groq("Hallo, wie gehts?") == "chat"


@patch("backend.prompt_routing.requests.post")
def test_classify_user_prompt_returns_chat_when_groq_says_chat(mock_post, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "chat"}}],
    }
    assert classify_user_prompt("Nur eine kurze Begrüßung und Smalltalk") == "chat"


def test_should_route_meta_generator_question_to_chat():
    assert should_route_direct_run_as_chat("was macht der generator") is True
    assert should_route_direct_run_as_chat("was macht der generato") is True
    assert should_route_direct_run_as_chat("überprüfe warum die app offline ist") is True


def test_should_route_not_false_positive_projekt():
    assert should_route_direct_run_as_chat("was macht die projektstruktur") is False


@patch("backend.prompt_routing.requests.post")
def test_classify_user_prompt_meta_chat_skips_groq(mock_post, monkeypatch):
    """Metafragen vor Groq → chat, kein HTTP."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert classify_user_prompt("was macht der generator") == "chat"
    mock_post.assert_not_called()


@patch("backend.prompt_routing.requests.post")
def test_classify_user_prompt_unknown_uses_heuristic_not_second_llm(mock_post, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    """Bei unknown vom ersten Call soll Heuristik greifen; kein zweiter POST für denselben Prompt."""
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "unknown"}}],
    }
    out = classify_user_prompt("Mach den Button in der Navigation rot")
    assert out == "project_task"
    assert mock_post.call_count == 1
