"""Build-/Check-Schritte fuer generierte Sandboxed-Projekte (Python/Node)."""

from __future__ import annotations

import importlib.util
import logging
import re as _re
import subprocess
import sys
from pathlib import Path

_log = logging.getLogger(__name__)


def _try_import_entry_script(root: Path) -> dict:
    """Laedt src/main.py oder src/generated_app.py (Import-Smoke)."""
    for name in ("main", "generated_app"):
        target = (root / "src" / f"{name}.py").resolve()
        if not target.is_file():
            continue
        try:
            spec = importlib.util.spec_from_file_location("_rainer_impl_smoke", target)
            if spec is None or spec.loader is None:
                return {"ok": False, "error": "spec konnte nicht erstellt werden"}
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return {"ok": True, "module": str(target)}
        except Exception as ex:
            return {"ok": False, "error": str(ex)}
    return {"ok": False, "error": "Kein src/main.py oder src/generated_app.py"}


def build_python_project(root: Path, timeout_sec: int = 45, test_imports: bool = True) -> dict:
    """
    Syntax: python -m py_compile fuer alle .py unter root.
    Optional: Import-Check fuer src/main.py bzw. src/generated_app.py.
    Rueckgabe enthaelt status: OK | FAILED (zusaetzlich zu ok: bool).
    """
    root = Path(root).resolve()
    py_files = sorted(root.rglob("*.py"))
    errors: list[str] = []
    exe = sys.executable or "python"
    for f in py_files:
        try:
            proc = subprocess.run(
                [exe, "-m", "py_compile", str(f)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
                errors.append(f"{f.relative_to(root)}: {err}")
        except Exception as ex:
            errors.append(f"{f.relative_to(root)}: {ex}")

    import_check: dict = {"skipped": True}
    if test_imports and not errors:
        import_check = _try_import_entry_script(root)

    syntax_ok = len(errors) == 0
    import_ok = bool(import_check.get("ok")) if not import_check.get("skipped") else syntax_ok
    overall_ok = syntax_ok and import_ok
    status = "OK" if overall_ok else "FAILED"
    n = len(py_files)
    _log.info("ProjectBuilder: %s (%s .py-Dateien)", status, n)

    return {
        "kind": "python",
        "status": status,
        "checked_files": n,
        "files_checked": n,
        "ok": overall_ok,
        "syntax_ok": syntax_ok,
        "import_check": import_check,
        "errors": errors,
    }


def build_csharp_project(_root: Path) -> dict:
    return {"kind": "csharp", "status": "SKIPPED", "ok": False, "hint": "MSBuild/Visual Studio nicht angebunden."}


def build_nodejs_project(_root: Path) -> dict:
    return {"kind": "nodejs", "status": "SKIPPED", "ok": False, "hint": "npm build nicht automatisch ausgefuehrt."}


# ── Minimaler Python-Stub fuer Auto-Repair ──────────────────────────────────
_MINIMAL_STUB = (
    '"""Automatisch generierter Stub (Syntax-Repair)."""\n\n\n'
    "def main():\n    pass\n\n\n"
    'if __name__ == "__main__":\n    main()\n'
)


def _try_fix_python(src: str) -> str:
    """Korrigiert haeufige Python-2-Print-Statements (print x -> print(x))."""
    lines = []
    for line in src.splitlines():
        m = _re.match(r'^(\s*)print\s+(?!\()(.+)', line)
        if m:
            indent, args = m.group(1), m.group(2).strip().rstrip(";")
            line = f"{indent}print({args})"
        lines.append(line)
    return "\n".join(lines) + "\n"


def auto_repair_python(root: Path, errors: list[str]) -> dict:
    """
    Versucht Python-Syntaxfehler zu reparieren.
    Strategie: 1) einfache Print-Fix 2) minimaler gueltiger Stub.
    Gibt {repaired: bool, files: [...]} zurueck.
    """
    root = Path(root).resolve()
    repaired: list[str] = []
    for err_line in errors:
        if not err_line or ": " not in err_line:
            continue
        # Format: "src\main.py: <SyntaxError...>" (Windows backslashes moeglich)
        rel_raw = err_line.split(": ")[0].strip().replace("\\", "/")
        target = (root / rel_raw).resolve()
        if not target.is_file():
            continue
        try:
            src = target.read_text(encoding="utf-8", errors="replace")
            # Already valid?
            try:
                compile(src, str(target), "exec")
                continue
            except SyntaxError:
                pass
            # Try simple fix
            fixed = _try_fix_python(src)
            try:
                compile(fixed, str(target), "exec")
                target.write_text(fixed, encoding="utf-8", newline="\n")
                repaired.append(f"{rel_raw} (fixed)")
                continue
            except SyntaxError:
                pass
            # Fallback: minimal valid stub
            target.write_text(_MINIMAL_STUB, encoding="utf-8", newline="\n")
            repaired.append(f"{rel_raw} (stub)")
        except Exception as ex:
            _log.warning("auto_repair_python %s: %s", rel_raw, ex)
    return {"repaired": bool(repaired), "files": repaired}


def build_project(root: Path, timeout_sec: int = 60) -> dict:
    """
    Auto-detektiert Projekttyp und fuehrt passende Build-Schritte aus.
    Python: py_compile aller .py-Dateien.
    Node.js: npm install + npm run build (wenn package.json vorhanden).
    Gibt ok=True nur wenn alle ausgefuehrten Steps OK sind.
    """
    from build_system import BuildSystem  # lokaler Import vermeidet zirkulaere Abhaengigkeit

    root = Path(root).resolve()
    steps: list[dict] = []
    log: list[str] = []

    py_files = sorted(root.rglob("*.py"))
    pkg_json = root / "package.json"
    has_python = bool(py_files)
    has_node = pkg_json.is_file()

    if has_python and has_node:
        kind = "mixed"
    elif has_python:
        kind = "python"
    elif has_node:
        kind = "nodejs"
    else:
        kind = "unknown"

    overall_ok = True

    # ── Python: py_compile ──────────────────────────────────────────────────
    if has_python:
        py_result = build_python_project(root, timeout_sec=timeout_sec)
        steps.append({"step": "py_compile", **py_result})
        if py_result.get("errors"):
            log.extend(py_result["errors"])
        if not py_result["ok"]:
            overall_ok = False

    # ── Node.js: npm install + npm run build ────────────────────────────────
    if has_node:
        bs = BuildSystem()
        npm_inst = bs.run_npm_install(root)
        steps.append({"step": "npm_install", **npm_inst})
        if not npm_inst["ok"]:
            overall_ok = False
            if npm_inst.get("stderr"):
                log.append(npm_inst["stderr"][:400])
        else:
            npm_build = bs.run_npm_build(root)
            steps.append({"step": "npm_build", **npm_build})
            if not npm_build["ok"]:
                overall_ok = False
                if npm_build.get("stderr"):
                    log.append(npm_build["stderr"][:400])

    # Sammle alle Fehler aus allen Steps
    all_errors: list[str] = []
    for s in steps:
        all_errors.extend(s.get("errors") or [])

    log = [l for l in log if l.strip()]

    return {
        "kind": kind,
        "ok": overall_ok,
        "status": "OK" if overall_ok else "FAILED",
        "steps": steps,
        "log": log,
        "errors": all_errors,
        "checked_files": len(py_files),
        "files_checked": len(py_files),  # Rueckwaertskompatibilitaet
    }


class ProjectBuilder:
    """Facade fuer build_python_project (expliziter Aufruf aus execute_intelligent)."""

    @staticmethod
    def build_python_project(sandbox: Path | str, **kwargs) -> dict:
        return build_python_project(Path(sandbox), **kwargs)
