"""Tests fuer hybrid_optimizer und intelligent-run-optimized."""

from __future__ import annotations

import hybrid_optimizer as ho_mod


def test_is_detailed_query_simple() -> None:
    opt = ho_mod.HybridOptimizer(ollama_url="http://127.0.0.1:9")
    assert not opt.is_detailed_query("Mach mir ein Tool")
    assert not opt.is_detailed_query("Was ist das?")
    assert not opt.is_detailed_query("Wie geht das?")


def test_is_detailed_query_complex() -> None:
    opt = ho_mod.HybridOptimizer(ollama_url="http://127.0.0.1:9")
    assert opt.is_detailed_query("Analysiere meinen Code")
    assert opt.is_detailed_query("Designe eine Architektur fuer Flask")
    assert opt.is_detailed_query("Optimiere die Performance")
    assert opt.is_detailed_query("Security Review fuer mein Tool")


def test_is_detailed_query_long_prompt() -> None:
    opt = ho_mod.HybridOptimizer(ollama_url="http://127.0.0.1:9")
    long_prompt = "Hallo " * 100
    assert opt.is_detailed_query(long_prompt)


def test_build_user_prompt_contains_parts() -> None:
    opt = ho_mod.HybridOptimizer(ollama_url="http://127.0.0.1:9")
    result = opt._build_user_prompt("Test Prompt", "Test Context", "quick")
    assert "Test Prompt" in result
    assert "Test Context" in result
    assert len(result) > 80


def test_execute_optimized_mock(monkeypatch) -> None:
    opt = ho_mod.HybridOptimizer(ollama_url="http://127.0.0.1:11434")

    class Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"response": "mocked", "eval_count": 5}

    monkeypatch.setattr(opt.session, "post", lambda *a, **k: Resp())
    out = opt.execute_optimized("kurze frage", context="ctx")
    assert out.get("success") is True
    assert out.get("response") == "mocked"
    assert out.get("mode") == "quick"


def test_intelligent_run_optimized_api(monkeypatch) -> None:
    import main as m

    monkeypatch.setattr(
        ho_mod.hybrid_optimizer,
        "execute_optimized",
        lambda *a, **k: {
            "success": True,
            "response": "ok",
            "model": "test-model",
            "mode": "quick",
            "elapsed_seconds": 0.01,
            "tokens_generated": 2,
            "quality_estimate": 4.0,
        },
    )

    def fake_arch(self):
        return "[ARCHITECTURE ANALYSIS]\nx\n[/ARCHITECTURE ANALYSIS]"

    monkeypatch.setattr("smart_tools.SmartTools.get_context_for_ollama", fake_arch)

    c = m.app.test_client()
    r = c.post("/api/intelligent-run-optimized", json={"task": "Hallo kurz"})
    assert r.status_code == 200
    body = r.get_json()
    assert body.get("ok") is True
    assert body.get("response") == "ok"
    assert body.get("final") is True
