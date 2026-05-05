"""Tests fuer smart_tools (AST-Scan, begrenzt)."""

from __future__ import annotations

from pathlib import Path

from smart_tools import SmartTools


def test_analyze_file_simple(tmp_path: Path) -> None:
    p = tmp_path / "mod.py"
    p.write_text(
        "import os\nclass A:\n    def m(self):\n        pass\ndef f():\n    return 1\n",
        encoding="utf-8",
    )
    st = SmartTools(project_root=tmp_path, max_scan_files=50)
    a = st.analyze_file("mod.py")
    assert "error" not in a
    assert a.get("lines", 0) >= 4
    assert any(c.get("name") == "A" for c in a.get("classes") or [])


def test_analyze_architecture_limited(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "backend" / "app.py").write_text("def main():\n    return\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert 1\n", encoding="utf-8")
    st = SmartTools(project_root=tmp_path, max_scan_files=30)
    analysis = st.analyze_architecture()
    assert "structure" in analysis
    assert analysis["total_files"] >= 1
    assert "modules" in analysis


def test_get_context_for_ollama(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    st = SmartTools(project_root=tmp_path, max_scan_files=20)
    ctx = st.get_context_for_ollama()
    assert "[ARCHITECTURE ANALYSIS]" in ctx
    assert "Projekt-Struktur:" in ctx
    assert "[/ARCHITECTURE ANALYSIS]" in ctx
    assert len(ctx) > 50
