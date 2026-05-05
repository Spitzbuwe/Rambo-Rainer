from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path


class WorkspaceIndexer:
    def __init__(self, root: Path, skip_dirs: set[str], allowed_write_prefixes: tuple[str, ...], sensitive_patterns: tuple[str, ...]):
        self.root = Path(root).resolve()
        self.skip_dirs = set(skip_dirs or set())
        self.allowed_write_prefixes = tuple(allowed_write_prefixes or tuple())
        self.sensitive_patterns = tuple(sensitive_patterns or tuple())

    def _classify_path(self, rel_path: str) -> dict:
        rel = str(rel_path or "").replace("\\", "/")
        parts = rel.split("/")
        area_key = parts[0] if len(parts) > 1 else "root"
        sensitive = rel in self.sensitive_patterns or any(p in rel for p in self.sensitive_patterns)
        allowed_write = (not sensitive) and any(rel.startswith(prefix) for prefix in self.allowed_write_prefixes)
        return {
            "path": rel,
            "area_key": area_key,
            "sensitive": sensitive,
            "allowed_write": allowed_write,
        }

    def scan_workspace(self) -> list[dict]:
        out: list[dict] = []
        for root, dirs, files in os.walk(self.root):
            root_path = Path(root)
            dirs[:] = sorted(d for d in dirs if d not in self.skip_dirs and not d.startswith("."))
            for name in sorted(files):
                if name.startswith("."):
                    continue
                rel = str((root_path / name).relative_to(self.root)).replace("\\", "/")
                out.append(self._classify_path(rel))
        return out

    def summarize_workspace(self, entries: list[dict]) -> dict:
        areas: dict[str, dict] = {}
        for item in entries or []:
            key = str(item.get("area_key") or "root")
            bucket = areas.setdefault(key, {"total": 0, "allowed_write": 0, "sensitive": 0})
            bucket["total"] += 1
            if bool(item.get("allowed_write")):
                bucket["allowed_write"] += 1
            if bool(item.get("sensitive")):
                bucket["sensitive"] += 1
        return areas

    def find_relevant_files(self, query: str, entries: list[dict], limit: int = 20) -> list[str]:
        q = str(query or "").lower().strip()
        if not q:
            return []
        ranked: list[tuple[int, str]] = []
        words = [w for w in q.replace("\\", "/").split() if w]
        for item in entries or []:
            p = str(item.get("path") or "")
            pl = p.lower()
            score = 0
            for w in words:
                if w in pl:
                    score += 2
            if any(seg in pl for seg in ("backend", "frontend", "tests")) and any(seg in q for seg in ("backend", "frontend", "test", "ui", "api")):
                score += 1
            if score > 0:
                ranked.append((score, p))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return [p for _, p in ranked[: max(1, int(limit))]]

    def build_workspace_index(self, *, sample_limit: int = 80) -> dict:
        entries = self.scan_workspace()
        return {
            "ok": True,
            "mode": "workspace_index",
            "root": str(self.root),
            "scanned_at": datetime.now().isoformat(timespec="seconds"),
            "total_files": len(entries),
            "areas": self.summarize_workspace(entries),
            "excluded_dirs": sorted(list(self.skip_dirs)),
            "sample_paths": [e.get("path") for e in entries[: max(1, int(sample_limit))] if e.get("path")],
            "writes_files": False,
            "notes": "Indexer liefert nur Strukturmetadaten und schreibt nichts.",
        }

    def health(self) -> dict:
        return {
            "ok": True,
            "root_exists": self.root.exists(),
            "mode": "workspace_index",
            "writes_files": False,
        }


_INSTANCE: WorkspaceIndexer | None = None


def get_instance(root: Path | None = None, skip_dirs: set[str] | None = None, allowed_write_prefixes: tuple[str, ...] | None = None, sensitive_patterns: tuple[str, ...] | None = None) -> WorkspaceIndexer:
    global _INSTANCE
    if _INSTANCE is None:
        if root is None:
            root = Path(".")
        _INSTANCE = WorkspaceIndexer(root, skip_dirs or set(), allowed_write_prefixes or tuple(), sensitive_patterns or tuple())
    return _INSTANCE
