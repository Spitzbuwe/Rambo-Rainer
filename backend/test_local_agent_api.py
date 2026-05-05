"""Smoke: /api/local-agent/capabilities und quick-run (ohne Ollama-Pflicht)."""


def test_local_agent_capabilities_ok():
    import main as m

    c = m.app.test_client()
    r = c.get("/api/local-agent/capabilities")
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("pricing") == "local_free"
    assert data.get("product") == "Rainer Build 3.0"
    assert "features" in data


def test_local_agent_quick_run_unknown_id():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/local-agent/quick-run", json={"id": "does_not_exist"})
    assert r.status_code == 400


def test_local_agent_quick_run_py_compile_write_action():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/local-agent/quick-run", json={"id": "py_compile_write_action"})
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("returncode") == 0


def test_local_agent_tool_read_file_ok():
    import main as m

    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/tool",
        json={"tool": "read_file", "rel_path": "backend/test_local_agent_api.py", "max_chars": 600},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    assert data.get("success") is True
    assert "test_local_agent" in (data.get("result") or "")
    assert (data.get("lines") or 0) > 0


def test_local_agent_tool_read_traversal_400():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/local-agent/tool", json={"tool": "read_file", "rel_path": "../../../etc/passwd"})
    assert r.status_code == 400


def test_local_agent_chat_includes_workspace_tag_by_default(monkeypatch):
    import main as m

    captured: dict = {}

    def fake_ollama(*args, **kwargs):
        captured["context"] = str(kwargs.get("context") or "")
        return "ok"

    monkeypatch.setattr(m, "call_ollama_intelligent", fake_ollama)
    c = m.app.test_client()
    r = c.post("/api/local-agent/chat", json={"message": "ping"})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True
    assert "[WORKSPACE]" in captured.get("context", "")


def test_local_agent_chat_workspace_tree_optional_off(monkeypatch):
    import main as m

    captured: dict = {}

    def fake_ollama(*args, **kwargs):
        ctx = kwargs.get("context")
        if ctx is None and len(args) > 1:
            ctx = args[1]
        captured["context"] = str(ctx or "")
        return "ok"

    monkeypatch.setattr(m, "call_ollama_intelligent", fake_ollama)
    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/chat",
        json={"message": "ping", "attach_workspace_tree": False},
    )
    assert r.status_code == 200
    assert "[WORKSPACE]" not in captured.get("context", "")


def test_local_agent_tool_unknown():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/local-agent/tool", json={"tool": "rm_rf"})
    assert r.status_code == 400


def test_local_agent_chat_attaches_workspace_file(monkeypatch):
    import main as m

    captured: dict = {}

    def fake_ollama(msg, context=None, model_override=None, **kwargs):
        captured["context"] = context or ""
        return "stub"

    monkeypatch.setattr(m, "call_ollama_intelligent", fake_ollama)
    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/chat",
        json={
            "message": "kurz",
            "attach_workspace_file": True,
            "workspace_rel": "backend/test_local_agent_api.py",
        },
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    ctx = captured.get("context", "")
    assert "[WORKSPACE_FILE" in ctx or "WORKSPACE_FILE" in ctx


def test_local_agent_tool_read_real_frontend_file():
    """Echte Projektdatei unter APP_DIR (frontend)."""
    import main as m

    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/tool",
        json={"tool": "read_file", "rel_path": "frontend/app.js", "max_chars": 1200},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    res = data.get("result") or ""
    assert "function" in res.lower() or "var " in res or "const " in res


def test_local_agent_tool_search_returns_matches_array():
    import main as m

    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/tool",
        json={"tool": "search", "query": "def safe_read_project_file", "file_pattern": "*.py", "max_matches": 15},
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("success") is True
    assert isinstance(data.get("matches"), list)
    assert data.get("total_matches", 0) >= 1
    assert data["matches"][0].get("file")


def test_local_agent_tool_search_hits_backend_module():
    """Suche nach eindeutigem Symbol in echten Dateien."""
    import main as m

    c = m.app.test_client()
    r = c.post(
        "/api/local-agent/tool",
        json={
            "tool": "search",
            "pattern": "def safe_read_project_file",
            "glob": "*.py",
            "max_matches": 20,
        },
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data.get("ok") is True
    out = data.get("result") or ""
    assert "local_agent_tools.py" in out


def test_local_agent_tool_search_empty_pattern_400():
    import main as m

    c = m.app.test_client()
    r = c.post("/api/local-agent/tool", json={"tool": "search", "pattern": "   ", "glob": "*.py"})
    assert r.status_code == 400


def test_local_agent_chat_includes_pytest_tail(monkeypatch):
    import main as m

    captured: dict = {}

    def fake_ollama(msg, context=None, model_override=None, **kwargs):
        captured["context"] = context or ""
        return "ok"

    monkeypatch.setattr(m, "call_ollama_intelligent", fake_ollama)
    c = m.app.test_client()
    tail = "FAILED test_x.py::test_foo - AssertionError: 1 != 2\n"
    r = c.post(
        "/api/local-agent/chat",
        json={"message": "was sagt der test?", "pytest_tail": tail},
    )
    assert r.status_code == 200
    assert r.get_json().get("ok") is True
    assert "[QUICK_CHECK_OUTPUT]" in captured.get("context", "")
    assert "AssertionError" in captured.get("context", "")


def test_local_agent_panel_flow_quick_run_output_usable_in_chat(monkeypatch):
    """Schnell-Check liefert stdout; gleicher Text kann als pytest_tail im Chat-Kontext landen."""
    import main as m

    captured: dict = {}

    def fake_ollama(msg, context=None, model_override=None, **kwargs):
        captured["context"] = context or ""
        return "stub"

    monkeypatch.setattr(m, "call_ollama_intelligent", fake_ollama)
    c = m.app.test_client()
    qr = c.post("/api/local-agent/quick-run", json={"id": "py_compile_main"})
    assert qr.status_code == 200
    qd = qr.get_json()
    blob = (qd.get("stdout") or "") + "\n" + (qd.get("stderr") or "")
    if not str(blob).strip():
        blob = "quick_run id=py_compile_main rc=" + str(qd.get("returncode"))
    r = c.post("/api/local-agent/chat", json={"message": "status?", "pytest_tail": blob[:4000]})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True
    ctx = captured.get("context", "")
    assert len(ctx) > 50
    assert "[QUICK_CHECK_OUTPUT]" in ctx
