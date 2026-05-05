"""Local sandbox workspace with snapshots, diff and rollback."""
from __future__ import annotations

import base64
import fnmatch
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

_EXCLUDED_PARTS = {
    "node_modules",
    "__pycache__",
    ".git",
    "dist",
    "build",
    ".rainer_agent",
    "Downloads",
}


def _safe_name(raw: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw.strip())
    return out.strip("_") or "workspace"


def _is_excluded(rel: Path, exclude_patterns: list[str] | None = None) -> bool:
    if any(part in _EXCLUDED_PARTS for part in rel.parts):
        return True
    if exclude_patterns:
        rel_posix = rel.as_posix()
        for pat in exclude_patterns:
            if fnmatch.fnmatch(rel_posix, pat):
                return True
    return False


def _is_included(rel: Path, include_patterns: list[str] | None = None) -> bool:
    if not include_patterns:
        return True
    rel_posix = rel.as_posix()
    return any(fnmatch.fnmatch(rel_posix, pat) for pat in include_patterns)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class AgentSandbox:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.base_dir = self.project_root / ".rainer_agent"
        self.sandboxes_root = self.base_dir / "sandboxes"
        self.snapshots_root = self.base_dir / "snapshots"
        self._counter = 0

    def _ensure_dirs(self) -> None:
        self.sandboxes_root.mkdir(parents=True, exist_ok=True)
        self.snapshots_root.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, name: str | None = None) -> dict[str, Any]:
        self._ensure_dirs()
        self._counter += 1
        ts = int(time.time() * 1000)
        ws_id = f"{_safe_name(name or 'workspace')}-{ts}-{self._counter:03d}"
        path = self.sandboxes_root / ws_id
        path.mkdir(parents=True, exist_ok=False)
        return {"ok": True, "workspace_id": ws_id, "path": str(path)}

    def workspace_path(self, workspace_id: str) -> Path:
        ws = self.sandboxes_root / _safe_name(workspace_id)
        return ws.resolve()

    def validate_workspace_path(self, path: str | Path) -> dict[str, Any]:
        self._ensure_dirs()
        p = Path(path).resolve()
        root = self.sandboxes_root.resolve()
        try:
            p.relative_to(root)
            return {"allowed": True, "path": str(p), "reason": "inside_sandbox"}
        except ValueError:
            return {"allowed": False, "path": str(p), "reason": "outside_sandbox"}

    def copy_project_subset(
        self,
        source_root: str | Path,
        workspace_id: str,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> dict[str, Any]:
        src = Path(source_root).resolve()
        ws = self.workspace_path(workspace_id)
        if not ws.exists():
            return {"ok": False, "reason": "workspace_missing", "workspace_id": workspace_id}
        copied = 0
        files: list[str] = []
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(src)
            if _is_excluded(rel, exclude_patterns):
                continue
            if not _is_included(rel, include_patterns):
                continue
            dst = ws / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            copied += 1
            files.append(rel.as_posix())
        return {"ok": True, "workspace_id": workspace_id, "copied_files": copied, "files": files}

    def _snapshot_workspace_files(self, ws: Path) -> dict[str, dict[str, Any]]:
        data: dict[str, dict[str, Any]] = {}
        for p in ws.rglob("*"):
            if not p.is_file():
                continue
            rel = p.relative_to(ws)
            if _is_excluded(rel):
                continue
            raw = p.read_bytes()
            try:
                text = raw.decode("utf-8")
                data[rel.as_posix()] = {"encoding": "utf-8", "content": text, "sha256": _hash_bytes(raw)}
            except UnicodeDecodeError:
                data[rel.as_posix()] = {
                    "encoding": "base64",
                    "content": base64.b64encode(raw).decode("ascii"),
                    "sha256": _hash_bytes(raw),
                }
        return data

    def create_snapshot(self, workspace_id: str, label: str | None = None) -> dict[str, Any]:
        self._ensure_dirs()
        ws = self.workspace_path(workspace_id)
        if not ws.exists():
            return {"ok": False, "reason": "workspace_missing", "workspace_id": workspace_id}
        snap_id = f"snap-{int(time.time() * 1000)}"
        bucket = self.snapshots_root / _safe_name(workspace_id)
        bucket.mkdir(parents=True, exist_ok=True)
        snap_file = bucket / f"{snap_id}.json"
        payload = {
            "snapshot_id": snap_id,
            "workspace_id": workspace_id,
            "label": label or "",
            "created_at": int(time.time()),
            "files": self._snapshot_workspace_files(ws),
        }
        snap_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "workspace_id": workspace_id, "snapshot_id": snap_id, "file_count": len(payload["files"])}

    def _load_snapshot(self, workspace_id: str, snapshot_id: str) -> dict[str, Any] | None:
        snap = self.snapshots_root / _safe_name(workspace_id) / f"{_safe_name(snapshot_id)}.json"
        if not snap.exists():
            return None
        return json.loads(snap.read_text(encoding="utf-8"))

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]:
        bucket = self.snapshots_root / _safe_name(workspace_id)
        if not bucket.exists():
            return []
        out: list[dict[str, Any]] = []
        for p in sorted(bucket.glob("*.json")):
            payload = json.loads(p.read_text(encoding="utf-8"))
            out.append(
                {
                    "snapshot_id": payload.get("snapshot_id", p.stem),
                    "label": payload.get("label", ""),
                    "file_count": len(payload.get("files", {})),
                    "created_at": payload.get("created_at", 0),
                }
            )
        return out

    def diff_snapshot(self, workspace_id: str, snapshot_id: str) -> dict[str, Any]:
        ws = self.workspace_path(workspace_id)
        snap = self._load_snapshot(workspace_id, snapshot_id)
        if not ws.exists() or snap is None:
            return {"ok": False, "reason": "workspace_or_snapshot_missing"}
        old_files: dict[str, dict[str, Any]] = snap.get("files", {})
        cur_files = self._snapshot_workspace_files(ws)
        old_keys = set(old_files)
        cur_keys = set(cur_files)
        added = sorted(cur_keys - old_keys)
        removed = sorted(old_keys - cur_keys)
        modified = sorted(k for k in (old_keys & cur_keys) if old_files[k].get("sha256") != cur_files[k].get("sha256"))
        return {"ok": True, "added": added, "modified": modified, "removed": removed}

    def rollback_snapshot(self, workspace_id: str, snapshot_id: str) -> dict[str, Any]:
        ws = self.workspace_path(workspace_id)
        val = self.validate_workspace_path(ws)
        if not val["allowed"]:
            return {"ok": False, "reason": "invalid_workspace_path"}
        snap = self._load_snapshot(workspace_id, snapshot_id)
        if not ws.exists() or snap is None:
            return {"ok": False, "reason": "workspace_or_snapshot_missing"}

        snapshot_files: dict[str, dict[str, Any]] = snap.get("files", {})
        current_files = self._snapshot_workspace_files(ws)
        snapshot_keys = set(snapshot_files)
        current_keys = set(current_files)

        removed_now = 0
        restored = 0

        for rel in sorted(current_keys - snapshot_keys):
            target = (ws / rel).resolve()
            if not self.validate_workspace_path(target)["allowed"]:
                continue
            target.unlink(missing_ok=True)
            removed_now += 1

        for rel, meta in snapshot_files.items():
            target = (ws / rel).resolve()
            if not self.validate_workspace_path(target)["allowed"]:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if meta.get("encoding") == "base64":
                raw = base64.b64decode(meta.get("content", ""))
                target.write_bytes(raw)
            else:
                target.write_text(str(meta.get("content", "")), encoding="utf-8")
            restored += 1
        return {"ok": True, "restored_files": restored, "removed_files": removed_now}

    def cleanup_workspace(self, workspace_id: str) -> dict[str, Any]:
        ws = self.workspace_path(workspace_id)
        if not ws.exists():
            return {"ok": True, "removed": False}
        val = self.validate_workspace_path(ws)
        if not val["allowed"]:
            return {"ok": False, "reason": "invalid_workspace_path"}
        shutil.rmtree(ws, ignore_errors=False)
        return {"ok": True, "removed": True}

    def sandbox_status(self, workspace_id: str | None = None) -> dict[str, Any]:
        self._ensure_dirs()
        if workspace_id:
            ws = self.workspace_path(workspace_id)
            exists = ws.exists()
            snapshots = self.list_snapshots(workspace_id) if exists else []
            return {
                "ok": True,
                "status": "ready",
                "workspace_id": workspace_id,
                "workspace_exists": exists,
                "snapshot_count": len(snapshots),
                "docker_available": shutil.which("docker") is not None,
            }
        workspaces = [p for p in self.sandboxes_root.iterdir() if p.is_dir()]
        return {
            "ok": True,
            "status": "ready",
            "workspace_count": len(workspaces),
            "base_dir": str(self.base_dir),
            "docker_available": shutil.which("docker") is not None,
        }

    def health(self) -> dict[str, Any]:
        self._ensure_dirs()
        return {
            "ok": True,
            "status": "ready",
            "module": "agent_sandbox",
            "base_dir": str(self.base_dir),
        }

    def describe(self) -> str:
        return "AgentSandbox"


_INSTANCE: AgentSandbox | None = None


def get_instance(project_root: Path | str | None = None) -> AgentSandbox:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentSandbox(project_root)
    return _INSTANCE


__all__ = ["AgentSandbox", "get_instance"]
