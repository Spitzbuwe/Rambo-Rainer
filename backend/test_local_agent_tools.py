"""Unit-Tests fuer local_agent_tools (ohne Flask)."""

from pathlib import Path

from local_agent_tools import safe_read_project_file, safe_search_project


def test_safe_read_ok(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("hello", encoding="utf-8")
    ok, text = safe_read_project_file(tmp_path, "sub/a.txt", 100)
    assert ok is True
    assert text == "hello"


def test_safe_read_traversal(tmp_path: Path) -> None:
    ok, msg = safe_read_project_file(tmp_path, "../outside", 100)
    assert ok is False


def test_safe_read_truncation(tmp_path: Path) -> None:
    long = "x" * 5000
    (tmp_path / "big.txt").write_text(long, encoding="utf-8")
    ok, text = safe_read_project_file(tmp_path, "big.txt", 800)
    assert ok is True
    assert len(text) <= 900
    assert "GEKUERZT" in text or len(text) < len(long)


def test_safe_search_hits(tmp_path: Path) -> None:
    (tmp_path / "m.py").write_text("def foo_bar_unique_xyz():\n    pass\n", encoding="utf-8")
    ok, out = safe_search_project(tmp_path, "foo_bar_unique_xyz", "*.py", max_matches=10)
    assert ok is True
    assert "m.py" in out
