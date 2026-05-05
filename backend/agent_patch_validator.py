from __future__ import annotations

from pathlib import Path


class PatchValidatorAgent:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.max_diff_lines = 250

    def _safe_rel(self, rel_path: str) -> str:
        rel = str(rel_path or "").replace("\\", "/").strip()
        if not rel or rel.startswith("/") or ".." in rel.split("/"):
            return ""
        return rel

    def validate_patch(self, *, rel_path: str, current_content: str, proposed_content: str, diff_text: str = "") -> dict:
        rel = self._safe_rel(rel_path)
        if not rel:
            return {"ok": False, "status": "invalid_path", "error": "Ungültiger Zielpfad."}

        target = (self.root / rel).resolve()
        try:
            target.relative_to(self.root)
        except Exception:
            return {"ok": False, "status": "outside_root", "error": "Pfad liegt außerhalb des erlaubten Bereichs."}

        current = str(current_content or "")
        proposed = str(proposed_content or "")
        if current == proposed:
            return {
                "ok": True,
                "status": "no_changes",
                "path": rel,
                "has_changes": False,
                "area_present": True,
                "allowed": True,
                "large_patch": False,
                "writes_files": False,
            }

        area_present = True if current.strip() else False
        dtext = str(diff_text or "")
        large_patch = (dtext.count("\n") + 1) > self.max_diff_lines if dtext else False

        return {
            "ok": True,
            "status": "validated" if not large_patch else "large_patch_blocked",
            "path": rel,
            "has_changes": True,
            "area_present": area_present,
            "allowed": True,
            "large_patch": large_patch,
            "writes_files": False,
            "block_reason": "Patch überschreitet sichere Diff-Schwelle." if large_patch else "",
        }


_INSTANCE: PatchValidatorAgent | None = None


def get_instance(root: Path | None = None) -> PatchValidatorAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PatchValidatorAgent(root or Path("."))
    return _INSTANCE
