from __future__ import annotations

import re
from pathlib import Path

from agent_patch_generator import PatchGeneratorAgent


class ErrorFixerAgent:
    __test__ = False

    def __init__(self, app_root: Path):
        self.app_root = Path(app_root).resolve()
        self.patch_generator = PatchGeneratorAgent(self.app_root)

    def _extract_paths(self, text: str) -> list[str]:
        raw = str(text or "")
        matches = re.findall(r"([A-Za-z0-9_\-./\\]+\.(?:py|js|ts|jsx|tsx|html|css|json|md))", raw)
        out: list[str] = []
        for m in matches:
            p = m.replace("\\", "/").strip()
            if not p or p.startswith("/") or ".." in p.split("/"):
                continue
            if p not in out:
                out.append(p)
        return out

    def _extract_failed_tests(self, text: str) -> list[str]:
        out = []
        for m in re.findall(r"(tests[\\/][A-Za-z0-9_./\\-]+::[A-Za-z0-9_./\\-]+)", str(text or "")):
            t = m.replace("\\", "/")
            if t not in out:
                out.append(t)
        return out

    def _categorize(self, check_name: str, output: str) -> str:
        t = f"{check_name} {output}".lower()
        if "timeoutexpired" in t or " timeout" in t:
            return "Timeout"
        if "syntaxerror" in t or "invalid syntax" in t:
            return "SyntaxError"
        if "importerror" in t or "modulenotfounderror" in t or "module not found" in t:
            return "ImportError"
        if "assertionerror" in t:
            return "AssertionError"
        return "UnknownError"

    def build_fix_plan(self, *, check_name: str, returncode: int, stdout: str = "", stderr: str = "") -> dict[str, object]:
        out = str(stdout or "")
        err = str(stderr or "")
        combined = (out + "\n" + err).strip()
        category = self._categorize(check_name, combined)
        files = self._extract_paths(combined)
        failed_tests = self._extract_failed_tests(combined)

        if not files:
            if "node_check_app" in str(check_name):
                files = ["frontend/app.js"]
            elif "py_compile_main" in str(check_name):
                files = ["backend/main.py"]
            elif "pytest" in str(check_name):
                files = ["tests"]

        risk = "medium" if category in {"SyntaxError", "AssertionError", "ImportError"} else "low"
        target_areas = []
        for f in files:
            if f.endswith(".py"):
                target_areas.append({"file": f, "area": "Python Funktion/Import/Assertion-naher Block"})
            elif f.endswith(".js"):
                target_areas.append({"file": f, "area": "JavaScript Funktion/Syntax-naher Block"})
            else:
                target_areas.append({"file": f, "area": "Fehlernaher Codebereich"})

        patch_entries = []
        for f in files:
            pg = self.patch_generator.generate_patch(
                f,
                "",
                "",
                task=f"Repair plan for {category} in {f}",
                context=combined[:400],
            )
            patch_entries.append(
                {
                    "file": f,
                    "planned_patch_summary": str(pg.get("reason") or "Minimalen Reparaturpatch vorbereiten."),
                    "target_area": str(pg.get("target_area") or "Fehlernaher Bereich"),
                    "risk": str(pg.get("risk") or risk.lower()),
                    "confidence": float(pg.get("confidence") or 0.7),
                    "writes_files": False,
                    "applied": False,
                }
            )

        steps = [
            "Fehlerausgabe analysieren",
            "Betroffene Datei(en) gezielt lesen",
            "Kleinen Reparatur-Patch vorbereiten",
            "Patch gegen Guard/Validator prüfen",
            "Betroffenen Check erneut ausführen",
        ]
        return {
            "ok": True,
            "status": "repair_plan_ready",
            "writes_files": False,
            "auto_apply": False,
            "check_name": str(check_name or ""),
            "returncode": int(returncode),
            "error_category": category,
            "affected_files": files,
            "failed_tests": failed_tests,
            "target_areas": target_areas,
            "risk": risk,
            "reason": "Testlauf fehlgeschlagen, Reparaturplan wurde erstellt.",
            "repair_plan": [
                {
                    "file": f,
                    "target_area": "Fehlernahe Code-Stelle",
                    "planned_change": "Minimalen Fix anwenden, der den gemeldeten Fehler behebt.",
                    "confidence": 0.72,
                }
                for f in files
            ],
            "repair_patch_plan": patch_entries,
            "step_engine_next_action": "context_read_then_patch_generate",
            "next_actions": [
                "context_read",
                "patch_generate",
                "patch_validate",
                "rerun_failed_check",
            ],
            "verification_checks": [str(check_name or "").strip()] if str(check_name or "").strip() else [],
            "steps": steps,
        }

    def health(self) -> dict[str, object]:
        return {"ok": True, "agent": "error_fixer", "app_root": str(self.app_root)}


_INSTANCE: ErrorFixerAgent | None = None


def get_instance(app_root: Path | None = None) -> ErrorFixerAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = ErrorFixerAgent(app_root or Path("."))
    return _INSTANCE
