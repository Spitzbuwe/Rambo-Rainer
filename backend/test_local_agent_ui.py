"""Smoke: lokale Agent-UI Strings in React-Quelle (ohne Browser)."""

from pathlib import Path


def _frontend_app() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "src" / "App.jsx"


def test_local_agent_banner_and_direct_button_in_html() -> None:
    html = _frontend_app().read_text(encoding="utf-8")
    assert "Rambo Rainer online. Gib mir einen Befehl." in html
    assert "rainerAgentOpen" in html
    assert "dash-chat-messages" in html


def test_local_agent_panel_markup() -> None:
    html = _frontend_app().read_text(encoding="utf-8")
    assert "setRainerAgentOpen" in html
    assert "<RainerAgent" in html
