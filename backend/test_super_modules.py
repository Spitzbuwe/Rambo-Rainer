from pathlib import Path

from build_system import BuildSystem
from electron_builder import ElectronBuilder
from prompt_optimizer import PromptOptimizer
from react_builder import ReactBuilder
from template_library import TemplateLibrary


def test_react_builder_generates_component_and_app():
    rb = ReactBuilder()
    code = rb.build_component({"component_name": "DemoComponent", "include_form": True, "include_validation": True})
    assert "function DemoComponent" in code
    app = rb.build_app_structure({"app_name": "DemoApp", "component_name": "DemoComponent"})
    assert "src/App.jsx" in app
    assert "package.json" in app


def test_electron_builder_generates_core_files():
    eb = ElectronBuilder()
    files = eb.build_complete_app({"app_name": "DesktopDemo"})
    assert "electron/main.js" in files
    assert "electron/preload.js" in files
    assert "electron/package.json" in files
    assert "BrowserWindow" in files["electron/main.js"]


def test_prompt_optimizer_detects_types():
    po = PromptOptimizer()
    assert po.detect_type("baue eine React app mit useState") == "react_app"
    assert po.detect_type("erstelle electron main.js preload") == "electron_app"
    assert po.detect_type("verarbeite icon png zu ico") == "icon"
    assert po.detect_type("run npm build und electron-builder") == "build"


def test_template_library_fill_template():
    out = TemplateLibrary.fill_template("react_component", component_name="HelloWidget")
    assert "HelloWidget" in out


def test_build_system_has_required_methods():
    bs = BuildSystem()
    assert callable(bs.run_npm_install)
    assert callable(bs.run_npm_build)
    assert callable(bs.run_electron_builder)


def test_super_builder_writes_real_files(tmp_path, monkeypatch):
    import main as m

    app_dir = tmp_path / "rambo_builder_local"
    app_dir.mkdir(parents=True, exist_ok=True)
    downloads_dir = tmp_path / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(m, "APP_DIR", app_dir)
    monkeypatch.setattr(m, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(m, "RAMBO_RAINER_ROOT", tmp_path)
    monkeypatch.setattr(m, "DOWNLOADS_DIR", downloads_dir)

    r1 = m.build_super_builder_result("Bitte erstelle eine electron desktop app mit preload und main.js")
    assert r1.get("executed") is True
    assert (downloads_dir / "electron" / "main.js").exists()
    assert (downloads_dir / "electron" / "assets" / "roboter_icon.png").exists()
    assert (downloads_dir / "rambo_ui" / "src" / "App.jsx").exists()
    assert (downloads_dir / "build_desktop.py").exists()

    r2 = m.build_super_builder_result("Erzeuge eine react app mit useState und Formular")
    assert r2.get("executed") is True
    assert (downloads_dir / "rambo_ui" / "src" / "App.jsx").exists()
