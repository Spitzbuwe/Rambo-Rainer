"""Incremental change tracker for smart rebuild/check recommendations."""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

_DEFAULT_PATTERNS = ("*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.html", "*.css", "*.json", "*.yml", "*.yaml", "*.md", "*.txt")
_IGNORED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".rainer_agent", "Downloads"}
_MAX_FILE_SIZE = 2_000_000


class AgentIncrementalTracker:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def file_hash(self, path: str | Path) -> str:
        p = Path(path)
        raw = p.read_bytes()
        return hashlib.sha256(raw).hexdigest()

    def scan_project(self, root: str | Path, patterns=None) -> dict:
        base = Path(root).resolve()
        pats = tuple(patterns or _DEFAULT_PATTERNS)
        files: dict[str, dict[str, Any]] = {}
        skipped: list[str] = []
        seen: set[Path] = set()

        for pat in pats:
            for p in base.rglob(pat):
                if p in seen:
                    continue
                seen.add(p)
                if not p.is_file():
                    continue
                rel = p.relative_to(base)
                if any(part in _IGNORED_DIRS for part in rel.parts):
                    continue
                if p.stat().st_size > _MAX_FILE_SIZE:
                    skipped.append(rel.as_posix())
                    continue
                raw = p.read_bytes()
                if b"\x00" in raw:
                    skipped.append(rel.as_posix())
                    continue
                files[rel.as_posix()] = {
                    "hash": hashlib.sha256(raw).hexdigest(),
                    "size": int(p.stat().st_size),
                    "mtime": float(p.stat().st_mtime),
                }
        return {"ok": True, "root": str(base), "files": files, "skipped_files": sorted(skipped)}

    def snapshot(self, root: str | Path, label: str | None = None) -> dict:
        scan = self.scan_project(root)
        return {
            "snapshot_id": f"snap-{uuid.uuid4().hex[:12]}",
            "label": label or "",
            "created_at": int(time.time()),
            "root": scan["root"],
            "files": scan["files"],
            "skipped_files": scan["skipped_files"],
        }

    def diff(self, snapshot_a: dict, snapshot_b: dict) -> dict:
        a = snapshot_a.get("files", {}) if isinstance(snapshot_a, dict) else {}
        b = snapshot_b.get("files", {}) if isinstance(snapshot_b, dict) else {}
        ka = set(a.keys())
        kb = set(b.keys())
        added = sorted(kb - ka)
        removed = sorted(ka - kb)
        modified = sorted(k for k in (ka & kb) if a[k].get("hash") != b[k].get("hash"))
        unchanged_count = sum(1 for k in (ka & kb) if a[k].get("hash") == b[k].get("hash"))
        return {"added": added, "modified": modified, "removed": removed, "unchanged_count": unchanged_count}

    def changed_files(self, root: str | Path, previous_snapshot: dict) -> dict:
        cur = self.snapshot(root, label="current")
        d = self.diff(previous_snapshot, cur)
        changed = sorted(set(d["added"] + d["modified"] + d["removed"]))
        return {"ok": True, "changed_files": changed, "diff": d, "current_snapshot": cur}

    def recommend_checks(self, changed_files: list[str]) -> dict:
        checks: list[str] = []
        hints: list[str] = []
        for f in changed_files:
            fp = f.replace("\\", "/")
            if fp.startswith("backend/") and fp.endswith(".py"):
                if "python -m py_compile backend\\main.py" not in checks:
                    checks.append("python -m py_compile backend\\main.py")
                if "python -m pytest tests -q" not in checks:
                    checks.append("python -m pytest tests -q")
            if fp.startswith("backend/agent_") and fp.endswith(".py"):
                fp_win = fp.replace("/", "\\")
                checks.append(f"python -m py_compile {fp_win}")
                stem = Path(fp).stem
                checks.append(f"python -m pytest tests/test_{stem}.py -q")
            if fp.startswith("frontend/") and fp.endswith(".js"):
                if "node --check frontend\\app.js" not in checks:
                    checks.append("node --check frontend\\app.js")
            if fp.startswith("frontend/") and (fp.endswith(".css") or fp.endswith(".html")):
                if "node --check frontend\\app.js" not in checks:
                    checks.append("node --check frontend\\app.js")
                hints.append("UI/manual check recommended")
            if fp == "package.json":
                hints.append("npm install may be required")
                checks.append("npm run build")
            if fp.startswith("tests/") and fp.endswith(".py"):
                fp_win = fp.replace("/", "\\")
                checks.append(f"python -m pytest {fp_win} -q")
        # dedupe preserving order
        dedup_checks = list(dict.fromkeys(checks))
        dedup_hints = list(dict.fromkeys(hints))
        return {"checks": dedup_checks, "hints": dedup_hints}

    def should_run_check(self, check_name: str, changed_files: list[str]) -> bool:
        rec = self.recommend_checks(changed_files)
        target = check_name.strip().lower()
        return any(c.lower() == target for c in rec["checks"])

    def export_snapshot(self, snapshot: dict) -> dict:
        # shallow validation for JSON compatibility
        json.dumps(snapshot, ensure_ascii=True, sort_keys=True)
        return dict(snapshot)

    def import_snapshot(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return {"ok": False, "reason": "invalid_payload"}
        if not isinstance(data.get("files"), dict):
            return {"ok": False, "reason": "missing_files"}
        return {"ok": True, "snapshot": data}

    def health(self) -> dict:
        return {"ok": True, "status": "ready", "module": "agent_incremental", "class": "AgentIncrementalTracker"}

    def describe(self) -> str:
        return "AgentIncrementalTracker"


_INSTANCE: AgentIncrementalTracker | None = None


def get_instance(project_root: Path | str | None = None) -> AgentIncrementalTracker:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentIncrementalTracker(project_root)
    return _INSTANCE


IncrementalRunner = AgentIncrementalTracker

__all__ = ["AgentIncrementalTracker", "IncrementalRunner", "get_instance"]
