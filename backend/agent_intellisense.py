from __future__ import annotations

import json
import keyword
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

FORBIDDEN_PREFIXES = (
    "../",
    "downloads/",
    "node_modules/",
    ".git/",
    "dist/",
    "build/",
    "__pycache__/",
    ".pytest_cache/",
)


def _is_forbidden(rel: str) -> bool:
    p = (rel or "").replace("\\", "/").strip().lower()
    return any(p.startswith(x) for x in FORBIDDEN_PREFIXES)


def _safe(project_root: Path, rel: str) -> Path:
    if _is_forbidden(rel):
        raise PermissionError("forbidden_path")
    p = (project_root / rel).resolve()
    if project_root not in p.parents:
        raise PermissionError("outside_project_root")
    return p


def _word_prefix(content: str, line: int, col: int) -> str:
    rows = content.splitlines()
    if line < 0 or line >= len(rows):
        return ""
    row = rows[line]
    col = max(0, min(col, len(row)))
    i = col
    while i > 0 and (row[i - 1].isalnum() or row[i - 1] == "_"):
        i -= 1
    return row[i:col]


def completions(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    fp = _safe(project_root, file)
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    prefix = _word_prefix(txt, int(line), int(col))
    words = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]{1,40}\b", txt))
    words.update(keyword.kwlist)
    items = [{"label": w, "kind": "text"} for w in sorted(words) if (not prefix or w.startswith(prefix))]
    return {"ok": True, "read_only": True, "items": items[:120], "prefix": prefix}


def signature_help(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    fp = _safe(project_root, file)
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    rows = txt.splitlines()
    if line < 0 or line >= len(rows):
        return {"ok": True, "read_only": True, "signature": None}
    row = rows[line][: max(0, min(col, len(rows[line])))]
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\($", row)
    if not m:
        return {"ok": True, "read_only": True, "signature": None}
    fn = m.group(1)
    return {"ok": True, "read_only": True, "signature": {"label": f"{fn}(...)", "activeParameter": 0}}


def code_actions(project_root: Path, file: str, line: int, col: int) -> dict[str, Any]:
    _safe(project_root, file)
    actions = [
        {"id": "extract_function", "title": "Extract Function (preview)", "writes_files": False},
        {"id": "rename_symbol", "title": "Rename Symbol (plan first)", "writes_files": False},
        {"id": "add_docstring", "title": "Add Docstring (preview)", "writes_files": False},
    ]
    return {"ok": True, "read_only": True, "actions": actions, "line": int(line), "col": int(col)}


def rename_plan(project_root: Path, file: str, old_symbol: str, new_symbol: str, pending: dict[str, Any]) -> dict[str, Any]:
    fp = _safe(project_root, file)
    if not old_symbol.strip() or not new_symbol.strip():
        return {"ok": False, "error": "invalid_symbols"}
    txt = fp.read_text(encoding="utf-8", errors="ignore")
    pat = re.compile(r"\b" + re.escape(old_symbol) + r"\b")
    matches = len(pat.findall(txt))
    if matches <= 0:
        return {"ok": False, "error": "symbol_not_found"}
    updated = pat.sub(new_symbol, txt)
    token = f"ren_{uuid4().hex[:12]}"
    pending[token] = {"file": file, "updated_content": updated, "old_symbol": old_symbol, "new_symbol": new_symbol, "used": False}
    return {
        "ok": True,
        "confirmation_token": token,
        "writes_files": False,
        "preview": {"file": file, "old_symbol": old_symbol, "new_symbol": new_symbol, "occurrences": matches},
        "auto_commit": False,
        "auto_rollback": False,
    }


def rename_apply(project_root: Path, token: str, pending: dict[str, Any]) -> dict[str, Any]:
    row = pending.get(token)
    if not row:
        return {"ok": False, "error": "invalid_token"}, 404
    if bool(row.get("used")):
        return {"ok": False, "error": "token_already_used"}, 409
    fp = _safe(project_root, str(row.get("file") or ""))
    fp.write_text(str(row.get("updated_content") or ""), encoding="utf-8")
    row["used"] = True
    pending[token] = row
    return {
        "ok": True,
        "writes_files": True,
        "affected_files": [str(row.get("file") or "")],
        "commit_performed": False,
        "rollback_performed": False,
    }, 200

