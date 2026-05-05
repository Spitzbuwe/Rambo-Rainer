from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BLOCK_PREFIXES = ("../", ".git/", "node_modules/", "dist/", "build/", "__pycache__/", ".pytest_cache/", "logs/", "data/snapshots/")


class WorkspaceSandbox:
    def __init__(self, app_dir: Path | str) -> None:
        self.app_dir = Path(app_dir).resolve()
        self.file = self.app_dir / "data" / "allowed_workspaces.json"
        self._ensure_default()

    def _ensure_default(self) -> None:
        s = self._load()
        if not s.get("allowed"):
            s["allowed"] = [{"id": "default", "path": str(self.app_dir), "trusted": False}]
            s["active_id"] = "default"
            self._save(s)

    def _load(self) -> dict[str, Any]:
        if not self.file.exists():
            return {"allowed": [], "active_id": ""}
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except Exception:
            return {"allowed": [], "active_id": ""}

    def _save(self, payload: dict[str, Any]) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_allowed_workspaces(self) -> dict[str, Any]:
        s = self._load()
        return {"ok": True, "allowed": list(s.get("allowed") or []), "active_id": s.get("active_id")}

    def add_allowed_workspace(self, path: str) -> dict[str, Any]:
        raw = str(path or "").strip()
        if not raw:
            return {"ok": False, "error": "path_empty", "errors": ["Kein Pfad angegeben."]}
        try:
            p = Path(raw).expanduser().resolve()
        except OSError as ex:
            return {"ok": False, "error": "path_invalid", "errors": [str(ex)]}
        sp = str(p)
        if sp.rstrip("\\/") in ("C:", "D:", "C:\\", "D:\\"):
            return {"ok": False, "error": "not_allowed_workspace", "errors": ["Laufwerkswurzel ist nicht erlaubt."]}
        if not p.exists():
            return {
                "ok": False,
                "error": "path_not_found",
                "path": sp,
                "errors": [f"Ordner existiert nicht: {sp}"],
            }
        if not p.is_dir():
            return {
                "ok": False,
                "error": "path_not_directory",
                "path": sp,
                "errors": [f"Pfad ist kein Verzeichnis: {sp}"],
            }
        s = self._load()
        wid = f"ws_{len(s.get('allowed') or []) + 1}"
        s.setdefault("allowed", []).append({"id": wid, "path": str(p), "trusted": False})
        self._save(s)
        return {"ok": True, "workspace": {"id": wid, "path": str(p)}}

    def remove_allowed_workspace(self, wid: str) -> dict[str, Any]:
        s = self._load()
        s["allowed"] = [x for x in list(s.get("allowed") or []) if str(x.get("id")) != str(wid)]
        if s.get("active_id") == wid:
            s["active_id"] = ""
        self._save(s)
        return {"ok": True}

    def select_workspace(self, path_or_id: str) -> dict[str, Any]:
        s = self._load()
        for w in list(s.get("allowed") or []):
            if str(w.get("id")) == str(path_or_id) or str(Path(w.get("path") or "").resolve()) == str(Path(path_or_id).resolve()):
                s["active_id"] = str(w.get("id"))
                self._save(s)
                return {"ok": True, "active": w}
        return {"ok": False, "error": "not_allowed_workspace"}

    def set_trusted(self, path_or_id: str, trusted: bool) -> dict[str, Any]:
        s = self._load()
        for w in list(s.get("allowed") or []):
            wid = str(w.get("id") or "")
            wpath = str(Path(w.get("path") or "").resolve())
            if wid == str(path_or_id) or wpath == str(Path(path_or_id).resolve()):
                w["trusted"] = bool(trusted)
                self._save(s)
                return {"ok": True, "workspace": w}
        return {"ok": False, "error": "not_allowed_workspace"}

    def get_active_workspace(self) -> dict[str, Any]:
        s = self._load()
        for w in list(s.get("allowed") or []):
            if str(w.get("id")) == str(s.get("active_id")):
                return {"ok": True, "active": w}
        return {"ok": False, "error": "no_active_workspace"}

    def is_path_allowed(self, rel_path: str) -> bool:
        p = (rel_path or "").replace("\\", "/").strip().lower()
        if any(p.startswith(x) for x in BLOCK_PREFIXES):
            return False
        act = self.get_active_workspace()
        if not act.get("ok"):
            return False
        root = Path((act.get("active") or {}).get("path") or self.app_dir).resolve()
        tgt = (root / rel_path).resolve()
        return root in tgt.parents or tgt == root

    def explain_block_reason(self, rel_path: str) -> str:
        p = (rel_path or "").replace("\\", "/").strip().lower()
        if any(p.startswith(x) for x in BLOCK_PREFIXES):
            return "forbidden_path"
        if "../" in p:
            return "path_traversal_blocked"
        return "outside_active_workspace"
