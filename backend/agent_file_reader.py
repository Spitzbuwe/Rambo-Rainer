from __future__ import annotations

from pathlib import Path


class FileReaderAgent:
    def __init__(self, root: Path, skip_dirs: set[str] | None = None):
        self.root = Path(root).resolve()
        self.skip_dirs = set(skip_dirs or set())

    def _is_allowed_rel(self, rel: str) -> bool:
        rel_norm = str(rel or "").replace("\\", "/").strip()
        if not rel_norm or rel_norm.startswith("/"):
            return False
        parts = rel_norm.split("/")
        if any(p in self.skip_dirs for p in parts):
            return False
        if ".." in parts:
            return False
        return True

    def find_relevant_files(self, query: str, *, limit: int = 5) -> list[str]:
        q = str(query or "").lower().strip()
        if not q:
            return []
        words = [w for w in q.replace("\\", "/").split() if w]
        ranked: list[tuple[int, str]] = []
        for p in self.root.rglob("*"):
            if not p.is_file():
                continue
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            if not self._is_allowed_rel(rel):
                continue
            pl = rel.lower()
            score = 0
            for w in words:
                if w in pl:
                    score += 2
            if ("frontend" in q and "frontend/" in pl) or ("backend" in q and "backend/" in pl) or ("test" in q and "tests/" in pl):
                score += 1
            if score > 0:
                ranked.append((score, rel))
        ranked.sort(key=lambda x: (-x[0], x[1]))
        return [rel for _, rel in ranked[: max(1, int(limit))]]

    def read_files(self, rel_paths: list[str], *, max_chars: int = 8000) -> list[dict]:
        out: list[dict] = []
        max_chars = max(200, int(max_chars or 8000))
        for rel in rel_paths:
            rel_norm = str(rel or "").replace("\\", "/").strip()
            if not self._is_allowed_rel(rel_norm):
                continue
            abs_path = (self.root / rel_norm).resolve()
            try:
                abs_path.relative_to(self.root)
            except Exception:
                continue
            if not abs_path.exists() or not abs_path.is_file():
                continue
            try:
                txt = abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                txt = ""
            out.append({
                "path": rel_norm,
                "content": txt[:max_chars],
                "truncated": len(txt) > max_chars,
                "length": len(txt),
            })
        return out

    def read_relevant_files(self, query: str, *, limit: int = 5, max_chars: int = 8000) -> dict:
        files = self.find_relevant_files(query, limit=limit)
        reads = self.read_files(files, max_chars=max_chars)
        return {
            "ok": True,
            "mode": "relevant_file_read",
            "query": str(query or ""),
            "selected_files": [r["path"] for r in reads],
            "file_count": len(reads),
            "files": reads,
            "notes": "Nur relevante Dateien wurden selektiv gelesen.",
            "reads_all_files": False,
        }


_INSTANCE: FileReaderAgent | None = None


def get_instance(root: Path | None = None, skip_dirs: set[str] | None = None) -> FileReaderAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = FileReaderAgent(root or Path("."), skip_dirs=skip_dirs or set())
    return _INSTANCE
