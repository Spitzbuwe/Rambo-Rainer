from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Any

FORBIDDEN = {"node_modules", "__pycache__", ".git", ".rainer_runs", "dist", "build"}
SUPPORTED = {".py", ".js", ".ts", ".jsx", ".tsx"}


def _safe_path(project_root: Path, rel_path: str) -> Path:
    p = (project_root / rel_path).resolve()
    if project_root not in p.parents and p != project_root:
        raise PermissionError("outside_project_root")
    return p


def _iter_files(project_root: Path):
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in FORBIDDEN and not d.startswith(".")]
        for f in files:
            if Path(f).suffix.lower() in SUPPORTED:
                yield Path(root) / f


def _word_at(content: str, line: int, col: int) -> str:
    rows = content.splitlines()
    if line < 0 or line >= len(rows):
        return ""
    row = rows[line]
    col = max(0, min(col, len(row)))
    a = col
    b = col
    while a > 0 and (row[a - 1].isalnum() or row[a - 1] == "_"):
        a -= 1
    while b < len(row) and (row[b].isalnum() or row[b] == "_"):
        b += 1
    return row[a:b].strip()


def _py_defs(file_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return out
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append({"name": n.name, "kind": "function", "line": n.lineno - 1, "col": n.col_offset})
        elif isinstance(n, ast.ClassDef):
            out.append({"name": n.name, "kind": "class", "line": n.lineno - 1, "col": n.col_offset})
    return out


def _js_defs(file_path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    txt = file_path.read_text(encoding="utf-8", errors="ignore")
    patterns = [
        (r"(?:function\s+)(\w+)\s*\(", "function"),
        (r"(?:class\s+)(\w+)", "class"),
        (r"(?:const|let|var)\s+(\w+)\s*=", "variable"),
        (r"export\s+(?:default\s+)?(?:function\s+|class\s+)?(\w+)", "export"),
    ]
    for i, row in enumerate(txt.splitlines()):
        for pat, kind in patterns:
            for m in re.finditer(pat, row):
                out.append({"name": m.group(1), "kind": kind, "line": i, "col": m.start(1)})
    return out


def go_to_definition(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    fp = _safe_path(project_root, file)
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    symbol = _word_at(txt, int(line), int(col))
    if not symbol:
        return {"ok": True, "status": "not_found", "symbol": None, "locations": [], "read_only": True}
    locations: list[dict[str, Any]] = []
    for src in _iter_files(project_root):
        defs = _py_defs(src) if src.suffix == ".py" else _js_defs(src)
        for d in defs:
            if d["name"] == symbol:
                locations.append({"file": src.relative_to(project_root).as_posix(), **d})
    return {"ok": True, "status": "ok" if locations else "not_found", "symbol": symbol, "locations": locations[:20], "read_only": True}


def find_references(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    fp = _safe_path(project_root, file)
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    symbol = _word_at(txt, int(line), int(col))
    if not symbol:
        return {"ok": True, "status": "not_found", "symbol": None, "references": [], "read_only": True}
    pat = re.compile(r"\b" + re.escape(symbol) + r"\b")
    refs: list[dict[str, Any]] = []
    suffix = fp.suffix.lower()
    for src in _iter_files(project_root):
        if suffix and src.suffix.lower() != suffix and suffix in {".js", ".ts", ".jsx", ".tsx", ".py"}:
            continue
        c = src.read_text(encoding="utf-8", errors="ignore")
        for i, row in enumerate(c.splitlines()):
            for m in pat.finditer(row):
                refs.append({"file": src.relative_to(project_root).as_posix(), "line": i, "col": m.start(), "preview": row.strip()[:120]})
    return {"ok": True, "status": "ok" if refs else "not_found", "symbol": symbol, "references": refs[:100], "total": len(refs), "read_only": True}


def hover_info(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    fp = _safe_path(project_root, file)
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    symbol = _word_at(txt, int(line), int(col))
    if not symbol:
        return {"ok": True, "status": "not_found", "markdown": "", "read_only": True}
    return {"ok": True, "status": "ok", "markdown": f"**{symbol}**", "read_only": True}


def symbols(project_root: Path) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for src in _iter_files(project_root):
        defs = _py_defs(src) if src.suffix == ".py" else _js_defs(src)
        for d in defs:
            out.append({"file": src.relative_to(project_root).as_posix(), **d})
    return {"ok": True, "count": len(out), "symbols": out[:2000], "read_only": True}


def diagnostics(project_root: Path, file: str = "") -> dict[str, Any]:
    targets = []
    if file:
        targets = [_safe_path(project_root, file)]
    else:
        targets = list(_iter_files(project_root))
    items: list[dict[str, Any]] = []
    for src in targets:
        if src.suffix == ".py":
            try:
                ast.parse(src.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError as e:
                items.append({"file": src.relative_to(project_root).as_posix(), "line": max(0, int(e.lineno or 1) - 1), "severity": "error", "message": str(e.msg or "syntax_error")})
        elif src.suffix in {".js", ".ts", ".jsx", ".tsx"}:
            txt = src.read_text(encoding="utf-8", errors="ignore")
            if txt.count("{") != txt.count("}"):
                items.append({"file": src.relative_to(project_root).as_posix(), "line": 0, "severity": "warning", "message": "brace_mismatch"})
            if txt.count("(") != txt.count(")"):
                items.append({"file": src.relative_to(project_root).as_posix(), "line": 0, "severity": "warning", "message": "paren_mismatch"})
    return {"ok": True, "diagnostics": items[:500], "count": len(items), "read_only": True}
