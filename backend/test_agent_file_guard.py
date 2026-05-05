"""Tests fuer agent_file_guard (ZIELORDNER-Block, Schreibschutz, Post-Checks)."""

from pathlib import Path

from agent_file_guard import (
    extract_relative_path_from_zielordner_block,
    looks_like_full_prompt_dump,
)
from write_action import execute_write_action


def test_zielordner_block_takes_precedence_over_other_paths():
    task = """
Irrelevant rambo_builder_local/frontend/ignored.js
ZIELORDNER
rambo_builder_local/backend/handler.py
ENDE_ZIELORDNER
"""
    assert extract_relative_path_from_zielordner_block(task) == "backend/handler.py"


def test_zielordner_block_relative_backend_path():
    task = """
ZIELORDNER
backend/foo.py
ENDE_ZIELORDNER
"""
    assert extract_relative_path_from_zielordner_block(task) == "backend/foo.py"


def test_looks_like_full_prompt_dump():
    head = "Du arbeitest im Projekt\nZiel:\nWichtig:\nPhase 0:\nPhase 1:\nAusgabeformat:\n"
    body = "x" * 5000
    assert looks_like_full_prompt_dump(head + body) is True
    assert looks_like_full_prompt_dump("print('hi')\n" * 20) is False


def test_protected_main_py_rejects_bulk_replace_without_patch(tmp_path):
    root = tmp_path / "rambo_builder_local"
    (root / "backend").mkdir(parents=True)
    p = root / "backend" / "main.py"
    p.write_text(("a\n" * 3000), encoding="utf-8")
    r = execute_write_action(p, ("b\n" * 3000), "backend/main.py", backup=True)
    assert r.get("ok") is False
    assert "geschuetzt" in (r.get("error") or "").lower() or "patch" in (r.get("error") or "").lower()
    assert p.read_text(encoding="utf-8").startswith("a\n")


def test_post_write_py_compile_failure_restores(tmp_path):
    root = tmp_path / "rambo_builder_local"
    (root / "backend").mkdir(parents=True)
    p = root / "backend" / "x.py"
    p.write_text("x = 1\n", encoding="utf-8")
    r = execute_write_action(p, "x = (\n", "backend/x.py", backup=True)
    assert r.get("ok") is False
    assert "Post-Check" in (r.get("error") or "") or "py_compile" in (r.get("error") or "").lower()
    assert p.read_text(encoding="utf-8") == "x = 1\n"


def test_small_write_to_data_unblocked(tmp_path):
    d = tmp_path / "rambo_builder_local" / "data"
    d.mkdir(parents=True)
    p = d / "note.txt"
    r = execute_write_action(p, "ok", "data/note.txt", backup=True)
    assert r.get("ok") is True
    assert p.read_text(encoding="utf-8") == "ok"
