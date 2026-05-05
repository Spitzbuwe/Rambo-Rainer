"""Zielpfad-Extraktion fuer Robot/Desktop-Builds (kein angeklebter Prompt-Text)."""

import pytest

SAMPLE = (
    r"C:\Users\mielersch\Desktop\Rambo-Rainer\Downloads\RainerRobotDesktop Ziel: Baue daraus "
    r"eine echte installierbare Windows-Desktop-App mit Electron, React\Vite und lokalem Backend-Management."
)

EXPECTED = r"C:\Users\mielersch\Desktop\Rambo-Rainer\Downloads\RainerRobotDesktop"


def test_strip_trailing_ziel_label():
    from main import _strip_trailing_prompt_from_windows_path_line

    assert _strip_trailing_prompt_from_windows_path_line(SAMPLE) == EXPECTED


def test_extract_robot_desktop_base_path_ziel_fragment():
    from main import _extract_robot_desktop_base_path_str

    assert _extract_robot_desktop_base_path_str(SAMPLE) == EXPECTED


def test_extract_prefers_rainerrobotdesktop_with_multiple_paths():
    from main import _extract_robot_desktop_base_path_str

    prompt = (
        "Quelle C:\\Users\\mielersch\\Desktop\\Rambo-Rainer\\Downloads\\Bild.png\n"
        "Arbeite in rambo_builder_local\\frontend\\app.js\n"
        f"Zielordner: {EXPECTED}\n"
        "Wichtig: npm install\n"
    )
    assert _extract_robot_desktop_base_path_str(prompt) == EXPECTED


def test_disallowed_rambo_builder_local_not_returned_as_target():
    from main import _extract_robot_desktop_base_path_str

    p = r"C:\Users\mielersch\Desktop\Rambo-Rainer\rambo_builder_local\frontend\app.js"
    assert _extract_robot_desktop_base_path_str(p) is None


LONG_DIRECT_RUN_PROMPT = f"""
Baue die komplette Electron Desktop-App mit React, Vite und electron-builder.

Arbeite direkt im Ordner und erzeuge eine installierbare Windows-App.

{SAMPLE}

Phase 1: electron/main.js, electron/preload.js
Phase 2: rambo_ui mit package.json und npm install
npm run build in rambo_ui, dann electron Ordner npm install
Komplette App, mehrere Dateien, Projekt-Struktur wie geplant.
Ausgabeformat: JSON mit Status.
"""


def test_post_direct_run_long_desktop_prompt_no_500(monkeypatch):
    """Flask test_client: project_build-Route, Pfad extrahiert korrekt, kein HTTP 500 (Build per Stub)."""
    import main as m

    def stub_execute_project_build(task, run_id, scope="project", mode="safe"):
        extracted = m._extract_robot_desktop_base_path_str(task)
        assert extracted == EXPECTED
        bp = extracted.replace("/", "\\")
        return {
            "run_id": run_id,
            "scope": scope,
            "mode": mode,
            "ok": True,
            "direct_status": "success",
            "build_status": "success",
            "message": "stub project build",
            "requires_confirmation": False,
            "requires_user_confirmation": False,
            "planned_files_count": 1,
            "created_files_count": 1,
            "missing_files": [],
            "created_files": [bp + "\\electron\\main.js"],
            "file_plan": ["electron/main.js"],
            "base_path": bp,
            "target_root": bp,
            "has_changes": True,
            "robot_build_auto_applied": True,
            "debug_auto_apply_decision": {"is_robot_desktop_build": True, "execution_route": "project_build"},
            "workstream_events": [],
            "recognized_task": {
                "task_type": "project_build",
                "primary_area": "Project Builder",
                "execution_route": "project_build",
            },
        }

    monkeypatch.setattr(m, "execute_project_build", stub_execute_project_build)
    client = m.app.test_client()
    resp = client.post(
        "/api/direct-run",
        json={
            "task": LONG_DIRECT_RUN_PROMPT,
            "prompt": LONG_DIRECT_RUN_PROMPT,
            "scope": "local",
            "mode": "apply",
            "auto_apply": True,
            "skip_review": True,
            "direct_execute": True,
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)[:800]
    data = resp.get_json()
    assert data is not None
    assert data.get("ok") is True
    norm = str(data.get("base_path") or "").replace("/", "\\").rstrip("\\").lower()
    assert norm == EXPECTED.lower()


def test_post_direct_run_outside_downloads_returns_400_json():
    """Pfad ausserhalb Downloads: strukturierte JSON-Antwort, kein HTTP 500."""
    import main as m

    bad_prompt = (
        "Baue komplette Electron React Vite Desktop-App mit phase 1 und npm install.\n"
        r"Zielordner: C:\Windows\Temp\NotInDownloadsBuild"
        "\nWichtig: electron-builder .exe\n"
    )
    client = m.app.test_client()
    resp = client.post(
        "/api/direct-run",
        json={
            "task": bad_prompt,
            "scope": "local",
            "mode": "apply",
            "auto_apply": True,
            "skip_review": True,
            "direct_execute": True,
        },
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data is not None
    assert data.get("ok") is False
    assert data.get("direct_status") == "failed"
    assert data.get("build_status") == "failed"
    assert data.get("base_path") in (None, "")
