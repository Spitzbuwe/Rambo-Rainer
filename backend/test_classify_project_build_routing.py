"""Routing: grosse Electron-/Desktop-Prompts -> project_build, nicht file_edit."""
from pathlib import Path

import pytest


def _sample_electron_desktop_txt() -> str:
    p = Path(__file__).resolve().parents[2] / "Downloads" / "Baue die komplette Electron Desktop.txt"
    if p.exists():
        return p.read_text(encoding="utf-8", errors="replace")
    # Fallback: Mindestinhalt wie Referenzdatei
    return """
Baue die komplette Electron Desktop-App mit Roboter-Icon!
Phase 1: Projekt-Struktur mit electron/ und rambo_ui/
Phase 2: electron/main.js
Phase 3: electron/preload.js
npm install und npm run build
Komplette App mit React und electron-builder -> .exe
""".lower()


def test_classify_electron_reference_is_project_build():
    from main import classify_direct_task

    text = _sample_electron_desktop_txt()
    r = classify_direct_task(text)
    assert r["task_type"] == "project_build", r


def test_classify_simple_single_file_is_not_project_build():
    from main import classify_direct_task

    r = classify_direct_task(
        'Erstelle nur die Datei rambo_builder_local\\frontend\\foo.txt mit dem Inhalt "hallo".'
    )
    assert r["task_type"] != "project_build"
    assert r["task_type"] in (
        "file_edit",
        "file_generation",
        "code_change",
        "unknown",
        "agent_instruction_prompt",
    )


def test_desktop_heuristic_not_single_file():
    from main import _is_desktop_multi_file_project_prompt, _is_single_file_direct_write_intent

    low = _sample_electron_desktop_txt().lower()
    assert _is_single_file_direct_write_intent(low) is False
    assert _is_desktop_multi_file_project_prompt(low) is True
