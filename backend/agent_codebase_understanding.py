from __future__ import annotations

import json
import re
from pathlib import Path


EXCLUDED_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", "data/snapshots"}


class CodebaseUnderstanding:
    def __init__(self, app_dir: Path):
        self.app_dir = app_dir.resolve()
        self.cache_file = (self.app_dir / "data" / "codebase_index.json").resolve()

    def _is_excluded(self, rel: str) -> bool:
        low = rel.replace("\\", "/").lower()
        return any(low == d or low.startswith(d + "/") for d in EXCLUDED_DIRS)

    def _scan_files(self) -> list[Path]:
        out: list[Path] = []
        for p in self.app_dir.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(self.app_dir).as_posix()
            if self._is_excluded(rel):
                continue
            out.append(p)
        return out

    def _symbols_for(self, rel: str, text: str) -> list[dict]:
        symbols: list[dict] = []
        for i, line in enumerate(text.splitlines(), 1):
            if rel.endswith(".py"):
                m = re.match(r"\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
                if m:
                    symbols.append({"name": m.group(1), "type": "function", "file": rel, "line": i, "kind": "python", "risk": "medium"})
                m = re.match(r"\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
                if m:
                    symbols.append({"name": m.group(1), "type": "class", "file": rel, "line": i, "kind": "python", "risk": "medium"})
                m = re.search(r'@app\.route\("([^"]+)"', line)
                if m:
                    symbols.append({"name": m.group(1), "type": "endpoint", "file": rel, "line": i, "kind": "flask_route", "risk": "high"})
            if rel.endswith(".js"):
                m = re.match(r"\s*(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)", line)
                if m:
                    symbols.append({"name": m.group(1), "type": "function", "file": rel, "line": i, "kind": "javascript", "risk": "medium"})
                m = re.match(r"\s*(?:const|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=", line)
                if m:
                    symbols.append({"name": m.group(1), "type": "variable", "file": rel, "line": i, "kind": "javascript", "risk": "low"})
        return symbols[:200]

    def rebuild(self) -> dict:
        files = self._scan_files()
        fmap = []
        symbols: list[dict] = []
        for p in files:
            rel = p.relative_to(self.app_dir).as_posix()
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                text = ""
            lang = "python" if rel.endswith(".py") else ("javascript" if rel.endswith(".js") else "other")
            purpose = "backend_api" if rel.startswith("backend/") else ("frontend_ui" if rel.startswith("frontend/") else "project_file")
            risk = "high" if rel in {"backend/main.py", "frontend/app.js"} else "medium"
            syms = self._symbols_for(rel, text)
            symbols.extend(syms)
            fmap.append({"file": rel, "type": "file", "language": lang, "size": len(text), "purpose_hint": purpose, "risk_level": risk, "important_symbols": [s["name"] for s in syms[:10]]})
        links = self._build_links(symbols)
        payload = {"ok": True, "map": fmap, "symbols": symbols, "links": links}
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
        return payload

    def _load(self) -> dict:
        if not self.cache_file.exists():
            return self.rebuild()
        try:
            return json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            return self.rebuild()

    def status(self) -> dict:
        data = self._load()
        return {"ok": True, "indexed_files": len(data.get("map") or []), "symbol_count": len(data.get("symbols") or []), "cache_file": "data/codebase_index.json"}

    def _build_links(self, symbols: list[dict]) -> list[dict]:
        backend_endpoints = [s for s in symbols if s.get("type") == "endpoint"]
        frontend_js = (self.app_dir / "frontend" / "app.js")
        text = frontend_js.read_text(encoding="utf-8", errors="ignore") if frontend_js.exists() else ""
        links = []
        for ep in backend_endpoints:
            endpoint = str(ep.get("name") or "")
            callers = []
            for i, line in enumerate(text.splitlines(), 1):
                if endpoint and endpoint in line and "fetchJSON(" in line:
                    callers.append({"file": "frontend/app.js", "line": i})
            links.append({"endpoint": endpoint, "backend_file": ep.get("file"), "backend_line": ep.get("line"), "frontend_callers": callers, "risk": "high" if "direct-confirm" in endpoint else "medium"})
        return links

    def links(self, endpoint: str = "") -> dict:
        rows = list(self._load().get("links") or [])
        if endpoint:
            rows = [r for r in rows if str(r.get("endpoint") or "") == endpoint]
        return {"ok": True, "links": rows, "count": len(rows)}

    def tests_map(self, target: str = "", endpoint: str = "") -> dict:
        tests = [p.relative_to(self.app_dir).as_posix() for p in (self.app_dir / "tests").glob("test_*.py")]
        selected = tests
        low_target = str(target or endpoint or "").lower()
        if "tools/execute" in low_target:
            selected = [t for t in tests if "tools" in t]
        elif "agent/run/start" in low_target:
            selected = [t for t in tests if "agent_run_controller_start" in t]
        elif "frontend/app.js" in low_target:
            selected = [t for t in tests if "agent_run_controller_start" in t or "level" in t]
        return {"ok": True, "tests": selected[:40], "count": len(selected[:40])}

    def impact(self, file: str = "", symbol: str = "", endpoint: str = "", feature: str = "") -> dict:
        target = " ".join([file, symbol, endpoint, feature]).lower()
        high = any(x in target for x in ["direct_confirm", "/api/direct-confirm", "backend/main.py"])
        level = "high" if high else ("medium" if target else "low")
        tests = self.tests_map(target=file, endpoint=endpoint).get("tests") or []
        checks = ["py_compile_main"] if "backend/" in file or "api/" in endpoint else []
        if "frontend/" in file:
            checks.append("node_check_app")
        if tests:
            checks.append(f"pytest {tests[0]} -q")
        return {"ok": True, "impact_level": level, "affected_files": [file] if file else [], "affected_endpoints": [endpoint] if endpoint else [], "affected_ui_functions": [symbol] if symbol else [], "affected_tests": tests[:8], "recommended_checks": checks or ["pytest_all"], "risk_reason": "core_flow_change" if high else "normal_change", "manual_review_required": high}
