from architecture_patterns import ArchitectureDecider
from decision_engine import DecisionMaker
from improvement_engine import ImprovementSuggester
from logic_engine import ProblemAnalyzer
from performance_optimizer import PerformanceOptimizer
from tradeoff_analyzer import TradeOffAnalyzer


def test_problem_analyzer_returns_structured_analysis():
    pa = ProblemAnalyzer()
    result = pa.analyze_problem("Bitte schnelle Windows App mit besserer Performance")
    assert result["actual_problem"]
    assert "constraints" in result
    assert "recommended_approach" in result


def test_decision_maker_selects_language_and_framework():
    dm = DecisionMaker()
    result = dm.make_technology_choice({
        "high_performance": True,
        "fast_development": False,
        "windows_only": True,
        "web_ui": False,
    })
    assert result["language"]["recommended"] in {"C#", "Rust", "Go"}
    assert result["framework"]["recommended"]


def test_tradeoff_analyzer_outputs_pros_cons_effort_risk():
    ta = TradeOffAnalyzer()
    result = ta.analyze_tradeoffs(["Python", "C#"])
    assert "pros" in result["Python"]
    assert "cons" in result["Python"]
    assert "effort" in result["Python"]
    assert "risk" in result["Python"]


def test_architecture_decider_recommends_pattern():
    ad = ArchitectureDecider()
    result = ad.recommend_architecture({"size": "large", "team_size": 8, "real_time": False, "ui_focus": True})
    assert result["recommended"] in ArchitectureDecider.PATTERNS
    assert isinstance(result["score"], int)


def test_improvement_and_performance_engines_return_actions():
    code = "def run(data):\n    for x in data:\n        for y in data:\n            print(x, y)\n"
    imp = ImprovementSuggester().analyze_code(code, "python")
    perf = PerformanceOptimizer().optimize(code, "python")
    assert imp["issues_found"] >= 1
    assert isinstance(perf["optimizations"], list)


def test_execute_intelligent_and_api_endpoint():
    import main as m

    result = m.execute_intelligent("Baue eine schnelle Windows App mit API")
    assert result["quick_mode"] is True
    assert result["detailed_mode"] is False
    assert result["workflow_mode"] == "quick"
    assert "analysis" in result
    assert "recommended_approach" in result
    assert "architecture" in result
    assert "generated_code" in result
    assert "improvements" in result
    assert "performance_optimizations" in result
    assert "formatted_response" in result
    assert result["final"] is True
    assert result["stop_continue"] is True
    assert "change_report" in result
    assert "visual" in result["change_report"]
    assert any(icon in result["formatted_response"] for icon in ["🎯", "🚀", "✅"])
    assert result["response_style"] in {"friendly", "developer", "business"}

    client = m.app.test_client()
    resp = client.post("/api/intelligent-run", json={"prompt": "Baue ein MVP mit Web UI"})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["quick_mode"] is True
    assert payload["detailed_mode"] is False
    assert payload["workflow_mode"] == "quick"
    assert "analysis" in payload
    assert "generated_code" in payload
    assert "formatted_response" in payload
    assert payload["final"] is True
    assert payload["stop_continue"] is True
    assert "change_report" in payload

    resp_dev = client.post("/api/intelligent-run", json={"prompt": "Bitte API Backend refactor", "response_style": "developer"})
    assert resp_dev.status_code == 200
    payload_dev = resp_dev.get_json()
    assert payload_dev["response_style"] == "developer"
    assert any(marker in payload_dev["formatted_response"] for marker in ["Engineer Notes", "Problem-Analyse", "Tech-Plan"])

    resp_auto = client.post("/api/intelligent-run", json={"prompt": "Bitte management update", "response_style": "auto"})
    assert resp_auto.status_code == 200
    payload_auto = resp_auto.get_json()
    assert payload_auto["response_style"] in {"business", "friendly", "developer"}

    resp_direct_auto = client.post("/api/direct-run", json={"task": "Rainer 3.0 intelligent run fuer management", "scope": "local", "mode": "safe", "response_style": "auto"})
    assert resp_direct_auto.status_code == 200
    payload_direct_auto = resp_direct_auto.get_json()
    assert payload_direct_auto.get("direct_status") == "completed"
    assert payload_direct_auto.get("formatted_response")
    assert payload_direct_auto.get("final") is True
    assert payload_direct_auto.get("stop_continue") is True

    resp_detailed = client.post("/api/intelligent-run", json={"prompt": "Analysiere und designe ein Windows-Tool mit API"})
    assert resp_detailed.status_code == 200
    payload_detailed = resp_detailed.get_json()
    assert payload_detailed["quick_mode"] is False
    assert payload_detailed["detailed_mode"] is True
    assert payload_detailed["workflow_mode"] == "detailed"


def test_implementation_sandbox():
    import shutil
    from pathlib import Path

    from file_creator import FileCreator

    base = Path(__file__).resolve().parent / "_test_impl_sandbox_tmp"
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    try:
        root = FileCreator.create_session_root(base)
        fc = FileCreator(root)
        assert fc.safe_path_check("src/x.txt") is True
        assert fc.safe_path_check("../evil.txt") is False
        fc.create_folder("src")
        fc.create_file("src/x.txt", "hello")
        p = root / "src" / "x.txt"
        assert p.read_text(encoding="utf-8").strip() == "hello"
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_run_implementation_phase_writes_sandbox(tmp_path, monkeypatch):
    import main as m
    from pathlib import Path

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(m, "DATA_DIR", data_dir)
    raw = {
        "generated_code": "def hello():\n    return 42\n",
        "recommended_approach": "Python Flask",
        "architecture": "monolith",
        "formatted_response": "Antwort",
    }
    out = m._run_implementation_phase("Dateien anlegen Test", raw)
    assert out.get("implementation") is True
    root = Path(out["implementation_root"])
    assert root.is_dir()
    assert (root / "src" / "main.py").is_file()
    assert (root / "README.md").is_file()
    assert (root / "requirements.txt").is_file()
    assert (root / "BUILD_RELEASE.md").is_file()
    assert out["implementation_build"].get("status") == "OK"
    assert out.get("implementation_summary")
    assert isinstance(out.get("implementation_files"), list)


def test_api_with_implementation_true(monkeypatch, tmp_path):
    import main as m

    monkeypatch.setattr(m, "call_ollama_intelligent", lambda *a, **k: "OK")
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(m, "DATA_DIR", data_dir)
    client = m.app.test_client()
    resp = client.post(
        "/api/intelligent-run",
        json={"task": "Kurztest mit Implementation", "implementation": True},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("implementation") is True
    assert body.get("implementation_root")
    assert isinstance(body.get("implementation_files"), list)
    assert body.get("implementation_build", {}).get("status") in {"OK", "FAILED"}


def test_keywords_trigger_implementation(monkeypatch, tmp_path):
    import main as m

    monkeypatch.setattr(m, "call_ollama_intelligent", lambda *a, **k: "x = 1\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(m, "DATA_DIR", data_dir)
    result = m.execute_intelligent("Bitte dateien erstellen fuer ein kleines Demo")
    assert result.get("implementation") is True
    assert result.get("implementation_root")


def test_implementation_creates_files(monkeypatch, tmp_path):
    """Implementation legt echte Dateien unter der Sandbox an."""
    import os
    import shutil

    import main as m

    monkeypatch.setattr(m, "call_ollama_intelligent", lambda *a, **k: "def main():\n    return 0\n")
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    monkeypatch.setattr(m, "DATA_DIR", data_dir)

    prompt = "Erstelle eine einfache Python-App mit Dateien"
    result = m.execute_intelligent(prompt, {"implementation": True})

    assert result.get("implementation") is True
    root = result.get("implementation_root")
    assert root
    impl_root = os.path.abspath(root)
    assert os.path.isdir(impl_root)
    assert len(os.listdir(impl_root)) > 0
    assert os.path.isfile(os.path.join(impl_root, "README.md"))
    assert os.path.isfile(os.path.join(impl_root, "src", "main.py"))
    assert os.path.isfile(os.path.join(impl_root, "requirements.txt"))
    assert os.path.isfile(os.path.join(impl_root, "BUILD_RELEASE.md"))
    assert result.get("implementation_summary")
    assert result.get("implementation_build", {}).get("status") == "OK"
    assert result.get("implementation_build", {}).get("files_checked", 0) >= 1

    shutil.rmtree(impl_root, ignore_errors=True)


def test_implementation_bundle_hello_prompt_prefers_console():
    """Konsolen-Prompt darf nicht durch generisches Flask-Stub-Code uebersteuert werden."""
    from code_generator_advanced import CodeGeneratorAdvanced

    flask_stub = '''from flask import Flask
app = Flask(__name__)

@app.route("/health")
def health():
    return "ok"
'''
    b = CodeGeneratorAdvanced.generate_implementation_bundle(
        "Die App soll hello ausgeben",
        {
            "generated_code": flask_stub,
            "recommended_approach": "Python",
            "architecture": "cli",
        },
    )
    main_src = next(f["content"] for f in b["files"] if f["rel"] == "src/main.py")
    req = next(f["content"] for f in b["files"] if f["rel"] == "requirements.txt")
    assert "hello" in main_src.lower()
    assert "print(" in main_src
    assert "Flask" not in main_src
    assert "flask" not in req.lower()
    compile(main_src, "<test_main>", "exec")


def test_code_generator_bundle_from_parts():
    from code_generator_advanced import CodeGeneratorAdvanced

    b = CodeGeneratorAdvanced.bundle_from_parts(
        "def x():\n    return 1\n",
        {"actual_problem": "Demo"},
        "layered",
        sandbox_root="/tmp/x",
    )
    assert b.get("files")
    rels = {f["rel"] for f in b["files"]}
    assert "README.md" in rels and "src/main.py" in rels and "requirements.txt" in rels
