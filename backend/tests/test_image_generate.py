from __future__ import annotations

import importlib


def _client():
    m = importlib.import_module("backend.main")
    m.app.config["TESTING"] = True
    return m.app.test_client()


def test_image_generate_rejects_empty_prompt():
    c = _client()
    r = c.post("/api/image/generate", json={"prompt": ""})
    assert r.status_code == 400
    body = r.get_json()
    assert body.get("ok") is False


def test_image_generate_rejects_too_long_prompt():
    c = _client()
    r = c.post("/api/image/generate", json={"prompt": "x" * 2001})
    assert r.status_code == 400


def test_image_generate_no_api_key_returns_502(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RAINER_IMAGE_API_KEY", raising=False)
    c = _client()
    r = c.post("/api/image/generate", json={"prompt": "ein roter Ballon"})
    assert r.status_code == 502
    body = r.get_json()
    assert body.get("ok") is False
    assert "API-Key" in str(body.get("error") or "")
