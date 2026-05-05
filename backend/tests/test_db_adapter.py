# -*- coding: utf-8 -*-
"""Tests DatabaseAdapter mit SQLite-Datei (Phase 17)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from db_adapter import DatabaseAdapter


@pytest.fixture
def adp(tmp_path):
    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    return DatabaseAdapter(db_url=url)


def test_save_and_get_rule(adp):
    rid = adp.save_rule({"fingerprint": "f1", "value": "hello"})
    assert rid == "f1"
    r = adp.get_rule("f1")
    assert r is not None
    assert r.get("value") == "hello"


def test_get_rule_missing(adp):
    assert adp.get_rule("nope") is None


def test_update_rule(adp):
    adp.save_rule({"fingerprint": "u1", "value": "a"})
    assert adp.update_rule("u1", {"value": "b"})
    assert adp.get_rule("u1").get("value") == "b"


def test_delete_rule(adp):
    adp.save_rule({"fingerprint": "d1"})
    assert adp.delete_rule("d1")
    assert adp.get_rule("d1") is None


def test_save_history_and_get(adp):
    adp.save_rule({"fingerprint": "h1"})
    hid = adp.save_history("h1", {"q": 1}, "act", True)
    assert hid is not None
    hist = adp.get_history("h1", limit=10)
    assert len(hist) == 1
    assert hist[0]["success"] is True


def test_get_history_sorted_newest_first(adp):
    adp.save_rule({"fingerprint": "s1"})
    adp.save_history("s1", {}, "a", False)
    adp.save_history("s1", {}, "b", True)
    h = adp.get_history("s1", limit=5)
    assert h[0]["output_action"] == "b"


def test_backup_to_json(adp, tmp_path):
    adp.save_rule({"fingerprint": "b1", "value": "x"})
    out = tmp_path / "exp.json"
    assert adp.backup_to_json(str(out))
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["learned_user_rules"]) >= 1


def test_restore_from_json(adp, tmp_path):
    p = tmp_path / "in.json"
    p.write_text(
        json.dumps({"learned_user_rules": [{"fingerprint": "r1", "value": "rv"}]}),
        encoding="utf-8",
    )
    assert adp.restore_from_json(str(p))
    assert adp.get_rule("r1")["value"] == "rv"


def test_fallback_when_orm_disabled(monkeypatch):
    monkeypatch.setattr("db_adapter._ORM_OK", False)
    ad = DatabaseAdapter()
    assert ad.available is False
    assert ad.save_rule({"fingerprint": "x"}) is None
    assert ad.get_all_rules() == []


def test_no_duplicate_primary_key(adp):
    adp.save_rule({"fingerprint": "uniq", "value": "1"})
    adp.save_rule({"fingerprint": "uniq", "value": "2"})
    rows = adp.get_all_rules()
    assert sum(1 for r in rows if r.get("fingerprint") == "uniq" or r.get("fingerprint") is None) <= 1
    assert adp.get_rule("uniq")["value"] == "2"
