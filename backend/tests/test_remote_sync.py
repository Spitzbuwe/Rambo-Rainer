# -*- coding: utf-8 -*-
"""Tests RemoteSyncManager (Phase 16)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from remote_sync import RemoteSyncManager


@pytest.fixture
def sync_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return str(d)


def test_register_agent_persists(sync_dir):
    m = RemoteSyncManager(sync_dir, admin_token="t")
    assert m.register_agent("a1", "http://127.0.0.1", 5036)
    data = json.loads(Path(m.agents_path).read_text(encoding="utf-8"))
    assert len(data["agents"]) == 1
    assert data["agents"][0]["id"] == "a1"
    assert data["agents"][0]["port"] == 5036


def test_get_connected_agents_lists_registered(sync_dir):
    m = RemoteSyncManager(sync_dir)
    m.register_agent("x", "http://h", 5000)
    agents = m.get_connected_agents()
    assert len(agents) == 1
    assert agents[0]["id"] == "x"


def test_push_rules_sends_post(monkeypatch, sync_dir):
    m = RemoteSyncManager(sync_dir, admin_token="tok")
    m.register_agent("t", "http://127.0.0.1", 9999)
    calls = []

    class R:
        status_code = 200

        def json(self):
            return {}

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return R()

    monkeypatch.setattr("remote_sync.requests.post", fake_post)
    ok = m.sync_rules("t", [{"fingerprint": "1", "value": "v"}])
    assert ok
    assert calls and "/api/rules/import" in calls[0][0]
    assert calls[0][1]["json"]["merge"] is True


def test_pull_rules_get_export(monkeypatch, sync_dir):
    m = RemoteSyncManager(sync_dir)
    m.register_agent("s", "http://127.0.0.1", 8888)

    class R:
        status_code = 200

        def json(self):
            return {"learned_user_rules": [{"fingerprint": "z"}]}

    monkeypatch.setattr("remote_sync.requests.get", lambda *a, **k: R())
    rules = m.pull_rules("s")
    assert len(rules) == 1
    assert rules[0]["fingerprint"] == "z"


def test_heartbeat_updates(sync_dir):
    m = RemoteSyncManager(sync_dir, heartbeat_timeout_s=300)
    m.register_agent("h", "http://x", 1)
    assert m.heartbeat("h")
    data = json.loads(Path(m.agents_path).read_text(encoding="utf-8"))
    assert data["agents"][0].get("last_heartbeat")


def test_heartbeat_timeout_marks_offline(sync_dir):
    m = RemoteSyncManager(sync_dir, heartbeat_timeout_s=0.01)
    m.register_agent("old", "http://x", 1)
    time.sleep(0.05)
    agents = m.get_connected_agents()
    assert agents[0]["connected"] is False


def test_agents_json_file_written(sync_dir):
    m = RemoteSyncManager(sync_dir)
    m.register_agent("p", "http://p", 7)
    assert Path(m.agents_path).is_file()


def test_double_register_updates(sync_dir):
    m = RemoteSyncManager(sync_dir)
    assert m.register_agent("d", "http://a", 1)
    assert m.register_agent("d", "http://b", 2)
    data = json.loads(Path(m.agents_path).read_text(encoding="utf-8"))
    assert len(data["agents"]) == 1
    assert data["agents"][0]["base_url"] == "http://b"
    assert data["agents"][0]["port"] == 2
