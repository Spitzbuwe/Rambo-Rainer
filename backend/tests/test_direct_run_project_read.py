# -*- coding: utf-8 -*-
"""direct_run: project_read nutzt AgentLoop.run_analysis (Phase 1.1)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import main


@patch("main.classify_user_prompt", return_value="project_read")
def test_direct_run_project_read_calls_run_analysis(_mock_pk, tmp_path: Path) -> None:
    (tmp_path / "sample.py").write_text("# sample", encoding="utf-8")
    mock_loop_cls = MagicMock()
    inst = MagicMock()
    inst.run_analysis.return_value = {
        "ok": True,
        "analysis": "UNITTEST_ANALYSE_MARKER",
        "files": ["sample.py"],
    }
    mock_loop_cls.return_value = inst
    with (
        patch("main.is_active_workspace_trusted", return_value=True),
        patch("main.get_active_project_root", return_value=tmp_path),
        patch("main.AgentLoop", mock_loop_cls),
    ):
        with main.app.test_client() as c:
            r = c.post(
                "/api/direct-run",
                json={"task": "analysiere das Projekt kurz", "scope": "local", "mode": "apply"},
            )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("classification") == "project_read"
    assert body.get("route_mode") == "agent_analysis"
    assert body.get("chat_response") == "UNITTEST_ANALYSE_MARKER"
    assert body.get("analysis_files") == ["sample.py"]
    mock_loop_cls.assert_called_once()
    inst.run_analysis.assert_called_once()


@patch("main.classify_user_prompt", return_value="project_read")
def test_direct_run_project_read_fallback_without_agent(_mock_pk, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1", encoding="utf-8")
    with (
        patch("main.is_active_workspace_trusted", return_value=True),
        patch("main.get_active_project_root", return_value=tmp_path),
        patch("main.AGENT_LOOP_AVAILABLE", False),
    ):
        with main.app.test_client() as c:
            r = c.post(
                "/api/direct-run",
                json={"task": "analysiere foo", "scope": "local", "mode": "apply"},
            )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("route_mode") == "read_only_analysis"
    details = " ".join(str((e or {}).get("detail") or "") for e in (body.get("workstream_events") or []))
    assert "Fallback" in details
