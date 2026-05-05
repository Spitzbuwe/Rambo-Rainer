from __future__ import annotations

import difflib
from pathlib import Path


class ChangeTracker:
    """Trackt geaenderte Dateien zwischen zwei Zustaenden."""

    def __init__(self):
        self.changes = []
        self.original_files = {}
        self._skip_parts = {
            ".git",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".cursor",
            ".vscode",
            ".idea",
        }
        self._skip_names = {"passive_learning.json"}

    def _iter_files(self, directory: str | Path):
        root = Path(directory)
        if not root.exists():
            return
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            parts = set(Path(rel).parts)
            if parts & self._skip_parts:
                continue
            if p.name in self._skip_names:
                continue
            yield p, rel

    def _read_file(self, path: Path) -> str:
        try:
            if path.stat().st_size > 1_000_000:
                return ""
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def capture_state(self, directory: str | Path):
        self.original_files = {}
        for path, rel in self._iter_files(directory):
            self.original_files[rel] = self._read_file(path)

    def _count_diff_lines(self, original: str, current: str) -> tuple[int, int]:
        added, removed = 0, 0
        for line in difflib.ndiff(original.splitlines(), current.splitlines()):
            if line.startswith("+ "):
                added += 1
            elif line.startswith("- "):
                removed += 1
        return added, removed

    def _generate_diff(self, original: str, current: str, file: str) -> str:
        diff = difflib.unified_diff(
            original.splitlines(),
            current.splitlines(),
            fromfile=f"a/{file}",
            tofile=f"b/{file}",
            lineterm="",
        )
        lines = list(diff)
        if len(lines) > 220:
            lines = lines[:220] + ["... (diff gekuerzt)"]
        return "\n".join(lines)

    def detect_changes(self, directory: str | Path):
        root = Path(directory)
        changes = []
        seen = set()
        for path, rel in self._iter_files(root):
            seen.add(rel)
            current = self._read_file(path)
            original = self.original_files.get(rel, "")
            if rel not in self.original_files:
                status = "created"
            elif current != original:
                status = "modified"
            else:
                continue
            added, removed = self._count_diff_lines(original, current)
            changes.append(
                {
                    "file": rel,
                    "status": status,
                    "original": original,
                    "current": current,
                    "diff": self._generate_diff(original, current, rel),
                    "lines_added": added,
                    "lines_removed": removed,
                }
            )
        for rel, original in self.original_files.items():
            if rel in seen:
                continue
            changes.append(
                {
                    "file": rel,
                    "status": "deleted",
                    "original": original,
                    "current": "",
                    "diff": self._generate_diff(original, "", rel),
                    "lines_added": 0,
                    "lines_removed": len(original.splitlines()),
                }
            )
        self.changes = changes
        return changes

    def build_file_tree(self, changes: list[dict]) -> list[dict]:
        tree = {}
        for c in changes:
            parts = Path(c["file"]).parts
            cursor = tree
            for idx, part in enumerate(parts):
                if idx == len(parts) - 1:
                    cursor.setdefault("__files__", []).append(
                        {"name": part, "status": c["status"], "path": c["file"]}
                    )
                else:
                    cursor = cursor.setdefault(part, {})

        def _flatten(node, prefix=""):
            out = []
            dirs = sorted([k for k in node.keys() if k != "__files__"])
            for d in dirs:
                full = f"{prefix}{d}/"
                out.append({"type": "dir", "path": full})
                out.extend(_flatten(node[d], prefix=full))
            for f in sorted(node.get("__files__", []), key=lambda x: x["name"]):
                out.append(
                    {
                        "type": "file",
                        "path": f"{prefix}{f['name']}",
                        "status": f["status"],
                    }
                )
            return out

        return _flatten(tree, "")

    def generate_visual_report(self, changes: list[dict]):
        summary = {
            "total": len(changes),
            "new": sum(1 for c in changes if c["status"] == "created"),
            "modified": sum(1 for c in changes if c["status"] == "modified"),
            "deleted": sum(1 for c in changes if c["status"] == "deleted"),
            "lines_added": sum(int(c["lines_added"]) for c in changes),
            "lines_removed": sum(int(c["lines_removed"]) for c in changes),
        }
        detailed = [
            {
                "file": c["file"],
                "status": c["status"],
                "diff": c["diff"],
                "stats": f"+{c['lines_added']} -{c['lines_removed']}",
                "lines_added": c["lines_added"],
                "lines_removed": c["lines_removed"],
            }
            for c in changes
        ]
        return {
            "file_tree": self.build_file_tree(changes),
            "summary": summary,
            "detailed_changes": detailed,
        }

    def generate_report(self, changes: list[dict]):
        visual = self.generate_visual_report(changes)
        return {
            "total_files": visual["summary"]["total"],
            "files_created": visual["summary"]["new"],
            "files_modified": visual["summary"]["modified"],
            "files_deleted": visual["summary"]["deleted"],
            "total_lines_added": visual["summary"]["lines_added"],
            "total_lines_removed": visual["summary"]["lines_removed"],
            "changes": visual["detailed_changes"],
            "visual": visual,
        }
