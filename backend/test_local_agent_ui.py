"""Smoke: statische UI-Strings im Frontend (ohne Browser)."""

from pathlib import Path


def _frontend_index() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "index.html"


def test_local_agent_banner_and_direct_button_in_html() -> None:
    html = _frontend_index().read_text(encoding="utf-8")
    assert "Nur Beratung" in html
    assert "Rainer Build 3.0" in html
    assert "localAgentApplySuggestionToDirect" in html
    assert "Vorschlag in Direktmodus" in html


def test_local_agent_panel_markup() -> None:
    html = _frontend_index().read_text(encoding="utf-8")
    assert 'data-view-target="local_agent"' in html
    assert "local-agent-thread" in html
