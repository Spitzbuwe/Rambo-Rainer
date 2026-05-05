"""
AST-basierte Projekt-Analyse (ohne externe Tools) fuer Ollama-Kontext.
"""
from __future__ import annotations

import ast
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SKIP_PARTS = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "dist-installer",
        ".venv",
        "venv",
        "_test_impl_sandbox_tmp",
    }
)


class SmartTools:
    """Analysiert Python-Dateien unter dem Projektroot (begrenzt)."""

    def __init__(self, project_root: Path | str | None = None, *, max_scan_files: int = 120) -> None:
        if project_root is None:
            self.project_root = Path(__file__).resolve().parents[1]
        else:
            self.project_root = Path(project_root).resolve()
        self.max_scan_files = max(10, min(int(max_scan_files), 400))
        self._cache: dict[str, Any] = {}

    def analyze_file(self, filepath: str) -> dict[str, Any]:
        rel = filepath.replace("\\", "/").lstrip("/")
        full_path = (self.project_root / rel).resolve()
        try:
            full_path.relative_to(self.project_root)
        except ValueError:
            return {"error": "Pfad ausserhalb Projektroot"}
        if not full_path.is_file():
            return {"error": f"Datei nicht gefunden: {filepath}"}
        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return {"error": str(e)}
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return {"error": f"SyntaxError: {e}"}

        analysis: dict[str, Any] = {
            "file": rel,
            "lines": len(content.splitlines()),
            "classes": [],
            "functions": [],
            "imports": [],
            "complexity": 0,
        }
        imports: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                analysis["classes"].append(
                    {
                        "name": node.name,
                        "methods": len([n for n in node.body if isinstance(n, ast.FunctionDef)]),
                        "line": node.lineno,
                    }
                )
            elif isinstance(node, ast.FunctionDef):
                analysis["functions"].append(
                    {"name": node.name, "args": len(node.args.args), "line": node.lineno}
                )
            elif isinstance(node, (ast.For, ast.While, ast.If)):
                analysis["complexity"] += 1

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

        analysis["imports"] = sorted(set(imports))
        return analysis

    def analyze_architecture(self) -> dict[str, Any]:
        cache_key = f"arch|{self.project_root}|{self.max_scan_files}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        modules: dict[str, Any] = {}
        total_lines = 0
        total_classes = 0
        total_functions = 0
        n = 0
        try:
            for py_file in sorted(self.project_root.glob("**/*.py")):
                if n >= self.max_scan_files:
                    break
                if any(p in py_file.parts for p in SKIP_PARTS):
                    continue
                try:
                    rel = str(py_file.relative_to(self.project_root)).replace("\\", "/")
                except ValueError:
                    continue
                a = self.analyze_file(rel)
                if "error" in a:
                    continue
                modules[rel] = a
                total_lines += int(a.get("lines") or 0)
                total_classes += len(a.get("classes") or [])
                total_functions += len(a.get("functions") or [])
                n += 1
        except OSError as e:
            logger.warning("analyze_architecture scan: %s", e)

        structure = self._infer_structure(modules)
        suggestions = self._generate_suggestions(modules)
        out = {
            "structure": structure,
            "total_files": len(modules),
            "total_lines": total_lines,
            "total_classes": total_classes,
            "total_functions": total_functions,
            "modules": modules,
            "suggestions": suggestions,
        }
        self._cache[cache_key] = out
        return out

    def _infer_structure(self, modules: dict[str, Any]) -> str:
        names = set(modules.keys())
        is_flask = any("main.py" in m or "app.py" in m for m in names)
        is_backend = any(m.startswith("backend/") for m in names)
        is_frontend = any("frontend" in m for m in names)
        has_tests = any("test" in m for m in names)
        parts: list[str] = []
        if is_flask:
            parts.append("Flask API")
        elif is_backend:
            parts.append("Backend")
        if is_frontend:
            parts.append("+ Frontend")
        if has_tests:
            parts.append("+ Tests")
        return " ".join(parts) if parts else "Python-Projekt"

    def _generate_suggestions(self, modules: dict[str, Any]) -> list[str]:
        suggestions: list[str] = []
        for module, analysis in modules.items():
            lines = int(analysis.get("lines") or 0)
            if lines > 500:
                suggestions.append(f"{module} ist gross ({lines} Zeilen) — evtl. teilen")
            imps = analysis.get("imports") or []
            if len(imps) > 15:
                suggestions.append(f"{module}: viele Imports ({len(imps)}) — Abhaengigkeiten pruefen")
            funcs = analysis.get("functions") or []
            if len(funcs) > 20:
                suggestions.append(f"{module}: viele Funktionen ({len(funcs)}) — Modularisierung pruefen")
        return suggestions[:8]

    def get_context_for_ollama(self) -> str:
        analysis = self.analyze_architecture()
        keys = list(analysis["modules"].keys())[:12]
        sug = analysis.get("suggestions") or []
        sug_txt = "\n".join(f"- {s}" for s in sug) if sug else "- (keine automatischen Hinweise)"
        return (
            "[ARCHITECTURE ANALYSIS]\n"
            f"Projekt-Struktur: {analysis['structure']}\n"
            f"Dateien (gescannt): {analysis['total_files']}\n"
            f"Code-Zeilen (Summe): {analysis['total_lines']}\n"
            f"Klassen: {analysis['total_classes']}  Funktionen: {analysis['total_functions']}\n"
            f"Beispiel-Dateien:\n{json.dumps(keys, indent=2, ensure_ascii=False)}\n"
            f"Verbesserungsvorschlaege:\n{sug_txt}\n"
            "[/ARCHITECTURE ANALYSIS]"
        )


def smart_tools_for_root(root: Path | str) -> SmartTools:
    return SmartTools(project_root=root)
