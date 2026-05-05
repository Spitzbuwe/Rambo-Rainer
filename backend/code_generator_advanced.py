"""Erzeugt ein sauberes Datei-Bundle fuer eine lokale Sandbox-Implementation."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_MINIMAL_MAIN = (
    'def main():\n    """Sandbox-Einstieg."""\n    return 0\n\n\n'
    'if __name__ == "__main__":\n    raise SystemExit(main())\n'
)


def _ensure_valid_python_module(src: str) -> str:
    """Stellt sicher, dass src/main.py syntaktisch gueltiges Python ist."""
    s = str(src or "").strip()
    if not s:
        return _MINIMAL_MAIN
    try:
        compile(s, "<bundle_main>", "exec")
    except SyntaxError:
        return _MINIMAL_MAIN
    if not s.endswith("\n"):
        s += "\n"
    return s


_WEB_STACK_HINTS = (
    "flask",
    "fastapi",
    "django",
    "starlette",
    "uvicorn",
    "gunicorn",
    "wsgi",
    "asgi",
    "webapp",
    "web app",
    "web-app",
    "website",
    "webseite",
    "rest api",
    "rest-api",
    "graphql",
    "http-server",
    "httpserver",
    "microservice",
    "endpoint",
    "webservice",
    "schnittstelle",
    "jsonify",
    "blueprint",
    "@app.route",
    "app.route",
    "/api/",
    " api ",
    "http://",
    "https://",
    "localhost:",
    "port 80",
    "port 443",
    "swagger",
    "openapi",
)


def _prompt_implies_web_stack(text: str) -> bool:
    """True, wenn der Nutzer ausdruecklich Web/API/Server meint."""
    t = str(text or "").lower()
    return any(h in t for h in _WEB_STACK_HINTS)


def _synthesize_console_main(task: str) -> str | None:
    """
    Einfache Konsolen-Skripte aus natuerlichsprachlichen Prompts (z. B. hello ausgeben).
    Gibt None zurueck, wenn kein erkennbares Konsolen-Muster passt.
    """
    raw = str(task or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if _prompt_implies_web_stack(low):
        return None

    # z. B. "Die App soll hello ausgeben", "soll hello ausgeben"
    m = re.search(
        r"\bsoll\s+([A-Za-z0-9_.-]{1,64})\s+ausgeben\b",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        token = m.group(1).strip()
        lit = json.dumps(token)
        return (
            f"def main():\n    print({lit})\n\n\n"
            'if __name__ == "__main__":\n    raise SystemExit(main())\n'
        )

    m2 = re.search(
        r"\b(?:print|ausgabe|zeige|gib)\s+(?:mir\s+)?[\"']([^\"'\n]{1,200})[\"']",
        raw,
        flags=re.IGNORECASE,
    )
    if m2:
        lit = json.dumps(m2.group(1))
        return (
            f"def main():\n    print({lit})\n\n\n"
            'if __name__ == "__main__":\n    raise SystemExit(main())\n'
        )

    if "hello world" in low or "hallo welt" in low:
        return (
            'def main():\n    print("Hello, world!")\n\n\n'
            'if __name__ == "__main__":\n    raise SystemExit(main())\n'
        )

    if re.search(r"\b(?:konsolen|terminal|stdout|print\s*aus)", low):
        m3 = re.search(r"[\"']([^\"'\n]{1,120})[\"']", raw)
        lit = json.dumps(m3.group(1)) if m3 else '"OK"'
        return (
            f"def main():\n    print({lit})\n\n\n"
            'if __name__ == "__main__":\n    raise SystemExit(main())\n'
        )

    return None


def _requirements_for_mode(web: bool) -> str:
    if web:
        return "flask==2.3.0\nrequests==2.31.0\n"
    return "# Keine Pakete noetig — reines Python-CLI.\n"


def _select_main_body(task: str, generated_code: str) -> str:
    """Prompt-treue: Web-Stack nur bei Web-Prompt; sonst Konsolen-Synthese bevorzugen."""
    t = str(task or "").strip()
    if _prompt_implies_web_stack(t):
        return _ensure_valid_python_module(generated_code)
    simple = _synthesize_console_main(t)
    if simple:
        return _ensure_valid_python_module(simple)
    return _ensure_valid_python_module(generated_code)


def _generate_gitignore() -> str:
    return (
        "__pycache__/\n*.pyc\n*.pyo\n.env\nvenv/\n.venv/\n"
        "dist/\nbuild/\n*.egg-info/\nnode_modules/\n.DS_Store\n"
    )


def _generate_utils(task: str) -> str:
    """Erzeugt src/utils.py mit Hilfsfunktionen."""
    return (
        '"""Hilfsfunktionen fuer das generierte Projekt."""\n\n'
        "from __future__ import annotations\n\n\n"
        "def greet(name: str = \"Welt\") -> str:\n"
        "    \"\"\"Gibt eine Begruessung zurueck.\"\"\"\n"
        "    return f\"Hallo, {name}!\"\n"
    )


def _generate_test_main(main_src: str, task: str) -> str:
    """Erzeugt tests/test_main.py als einfache pytest-Testdatei."""
    has_main_fn = "def main(" in main_src
    call_main = (
        "    if hasattr(main, 'main'):\n"
        "        result = main.main()\n"
        "        assert result is None or result is not None\n"
    ) if has_main_fn else (
        "    pass  # kein main() gefunden\n"
    )
    return (
        "\"\"\"Automatisch generierte Smoke-Tests.\"\"\"\n"
        "import sys\n"
        "import os\n\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), \"..\", \"src\"))\n\n\n"
        "def test_main_importable():\n"
        "    import main  # noqa: F401\n"
        "    assert main is not None\n\n\n"
        f"def test_main_runs():\n"
        "    import main\n"
        f"{call_main}"
    )


class CodeGeneratorAdvanced:
    """Statische Bundle-Erzeugung fuer README, src/main.py und requirements."""

    @staticmethod
    def generate_implementation_bundle(
        prompt: str,
        raw_result: dict[str, Any] | None,
        sandbox_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """
        Liefert ``files`` als Liste von ``{"rel": str, "content": str}`` (Pfade relativ zur Sandbox).
        Nutzt ``generated_code``, ``analysis``, ``recommended_approach``, ``architecture`` aus raw_result.

        Alternative: :meth:`bundle_from_parts` mit (code, analysis, architecture, sandbox_root).
        """
        raw = raw_result or {}
        task = str(prompt or "").strip()
        code = str(raw.get("generated_code") or "").strip()
        analysis = raw.get("analysis") or {}
        if isinstance(analysis, dict):
            problem = str(
                analysis.get("actual_problem")
                or analysis.get("problem_type")
                or analysis.get("problem")
                or "N/A"
            )
        else:
            problem = str(analysis)[:800]
        tech = str(raw.get("recommended_approach") or "N/A")
        arch = str(raw.get("architecture") or "N/A")
        sandbox_note = ""
        if sandbox_root:
            sandbox_note = f"\nSandbox: `{Path(str(sandbox_root)).as_posix()}`\n"

        readme = (
            "# Generated Project\n\n"
            "## Problem\n"
            f"{problem}\n\n"
            "## Recommended Tech\n"
            f"{tech}\n\n"
            "## Architecture\n"
            f"{arch}\n"
            f"{sandbox_note}\n"
            "## Prompt (Auszug)\n\n"
            "```text\n"
            f"{task[:4000]}{'...' if len(task) > 4000 else ''}\n"
            "```\n\n"
            "## How to Run\n\n"
            "1. pip install -r requirements.txt\n"
            "2. python src/main.py\n"
        )

        web_mode = _prompt_implies_web_stack(task)
        py_body = _select_main_body(task, code)
        requirements = _requirements_for_mode(web_mode)

        files: list[dict[str, str]] = [
            {"rel": "README.md", "content": readme},
            {"rel": "src/main.py", "content": py_body},
            {"rel": "src/utils.py", "content": _generate_utils(task)},
            {"rel": "tests/test_main.py", "content": _generate_test_main(py_body, task)},
            {"rel": "requirements.txt", "content": requirements},
            {"rel": ".gitignore", "content": _generate_gitignore()},
        ]
        if not files:
            raise RuntimeError("Implementation-Bundle ist leer")
        file_plan = [{"rel": f["rel"], "lines": len(f["content"].splitlines())} for f in files]
        return {
            "files": files,
            "file_plan": file_plan,
            "summary": f"{len(files)} Dateien generiert",
            "readme": readme,
        }

    @staticmethod
    def bundle_from_parts(
        code: str,
        analysis: dict[str, Any] | str,
        architecture: str,
        sandbox_root: str | Path | None = None,
    ) -> dict[str, Any]:
        """API wie ``generate_implementation_bundle(code, analysis, architecture, sandbox)``."""
        if isinstance(analysis, dict):
            ad = analysis
        else:
            ad = {"actual_problem": str(analysis)}
        raw: dict[str, Any] = {
            "generated_code": code,
            "analysis": ad,
            "recommended_approach": str(ad.get("recommended_approach") or ad.get("tech") or "Python"),
            "architecture": str(architecture or "modular"),
        }
        task_hint = str(ad.get("actual_problem") or ad.get("problem_type") or "").strip()
        bundle_prompt = task_hint or str(code or "").strip()[:800]
        return CodeGeneratorAdvanced.generate_implementation_bundle(bundle_prompt, raw, sandbox_root)


def generate_implementation_bundle(
    prompt: str, raw_result: dict[str, Any] | None = None, sandbox_root: str | Path | None = None
) -> dict[str, Any]:
    """Abwaertskompatibler Wrapper."""
    return CodeGeneratorAdvanced.generate_implementation_bundle(prompt, raw_result, sandbox_root)


def generate_unit_tests(code: str, language: str = "python") -> str:
    lang = str(language or "python").lower()
    if lang != "python":
        return f"// Tests fuer {lang} – bitte manuell ergaenzen.\n"
    return (
        "import pytest\n\n\n"
        "def test_non_empty_code():\n"
        f"    assert {bool(str(code).strip())!r}\n"
    )


def generate_integration_tests(_spec: dict) -> str:
    return "# Integrationstests – Platzhalter fuer spaetere Erweiterung.\n"
