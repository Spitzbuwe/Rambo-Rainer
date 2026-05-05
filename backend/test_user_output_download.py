"""Dualer Output: intern (APP_DIR) vs. USER-Downloads bei Prompt-Schluesselwoertern."""
from pathlib import Path

import pytest


def test_local_user_download_requested():
    import main

    assert main.local_user_download_requested(
        "Erstelle file1.txt mit content1 und speichere als Download"
    )
    assert main.local_user_download_requested("Bitte save as download nach file1.txt")
    assert not main.local_user_download_requested("Erstelle file1.txt mit content1")


def test_resolve_user_download_path(tmp_path, monkeypatch):
    import main

    user_dl = tmp_path / "Downloads"
    user_dl.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "get_user_output_dir", lambda: user_dl.resolve())

    task = "Erstelle file1.txt mit content1 und speichere als Download"
    resolved, rel, err = main.resolve_local_target_path("file1.txt", task)
    assert err is None
    assert rel == "Downloads/file1.txt"
    assert resolved == user_dl / "file1.txt"


def test_resolve_user_download_strips_downloads_prefix(tmp_path, monkeypatch):
    import main

    user_dl = tmp_path / "Downloads"
    user_dl.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "get_user_output_dir", lambda: user_dl.resolve())

    task = "speichere als Download"
    resolved, rel, err = main.resolve_local_target_path("Downloads/file1.txt", task)
    assert err is None
    assert rel == "Downloads/file1.txt"
    assert resolved == user_dl / "file1.txt"


def test_resolve_internal_without_keyword(tmp_path, monkeypatch):
    import main

    fake_app = tmp_path / "rambo_builder_local"
    fake_app.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "APP_DIR", fake_app)

    resolved, rel, err = main.resolve_local_target_path("data/_audit_internal.txt", None)
    assert err is None
    assert rel == "data/_audit_internal.txt"
    assert resolved == fake_app / "data" / "_audit_internal.txt"


def test_write_to_user_download_roundtrip(tmp_path, monkeypatch):
    import main
    from routes import persist_text_file_change

    user_dl = tmp_path / "Downloads"
    user_dl.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(main, "get_user_output_dir", lambda: user_dl.resolve())

    task = "speichere als Download"
    resolved, rel, err = main.resolve_local_target_path("file_roundtrip.txt", task)
    assert err is None
    wr = persist_text_file_change(resolved, "hello-download", rel)
    assert wr.get("ok") is True
    assert (user_dl / "file_roundtrip.txt").read_text(encoding="utf-8") == "hello-download"
