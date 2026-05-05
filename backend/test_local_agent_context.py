"""Kontext-Packaging (Workspace-Baum, Such-Treffer-Parsing)."""

from pathlib import Path

from local_agent_context import build_workspace_tree_snippet, parse_search_result_lines


def test_build_workspace_tree_contains_backend(tmp_path: Path) -> None:
    (tmp_path / "backend").mkdir()
    (tmp_path / "frontend").mkdir()
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    tree = build_workspace_tree_snippet(tmp_path, 30)
    assert "backend/" in tree or "backend" in tree
    assert tmp_path.name in tree


def test_parse_search_result_lines() -> None:
    raw = "backend/foo.py:12:def hello():\nfrontend/x.js:3:export const a = 1"
    hits = parse_search_result_lines(raw)
    assert len(hits) == 2
    assert hits[0]["file"] == "backend/foo.py"
    assert hits[0]["line"] == 12
    assert "hello" in str(hits[0]["content"])
