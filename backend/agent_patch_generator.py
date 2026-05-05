from __future__ import annotations

import difflib
from pathlib import Path


class PatchGeneratorAgent:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.max_diff_lines = 250

    def _safe_rel(self, rel_path: str) -> str:
        rel = str(rel_path or "").replace("\\", "/").strip()
        if not rel or rel.startswith("/") or ".." in rel.split("/"):
            return ""
        return rel

    def _infer_file_meta(self, rel_path: str, task: str = "") -> dict:
        p = str(rel_path or "").replace("\\", "/")
        t = str(task or "").lower()
        risk = "low"
        target_area = "Dateiinhalt"
        reason = "Gezielte Änderung gemäß Aufgabe."
        confidence = 0.75
        if p.endswith("frontend/app.js"):
            risk = "medium"
            target_area = "UI-Logik / Event-Handling / Rendering"
            reason = "Frontend-Steuerung und Ergebnisdarstellung anpassen."
            confidence = 0.8
        elif p.endswith("backend/main.py"):
            risk = "medium"
            target_area = "API-Routing / Guard-Logik"
            reason = "Backend-Flow und Endpunktverhalten stabilisieren."
            confidence = 0.78
        elif p.endswith("frontend/style.css") or p.endswith("frontend/index.html"):
            risk = "low"
            target_area = "UI-Struktur / Styling"
            reason = "Darstellung und Bedienbarkeit sicherstellen."
            confidence = 0.82
        if "rewrite" in t or "komplett" in t or "full" in t:
            risk = "high"
            confidence = min(confidence, 0.65)
            reason = "Aufgabe deutet auf größere Änderungen hin."
        return {
            "risk": risk,
            "reason": reason,
            "target_area": target_area,
            "confidence": confidence,
        }

    def _generate_single_patch(self, rel_path: str, current_content: str, proposed_content: str, task: str = "") -> dict:
        rel = self._safe_rel(rel_path)
        if not rel:
            return {"ok": False, "error": "Ungültiger Zielpfad."}
        before = str(current_content or "")
        after = str(proposed_content or "")
        diff_lines = list(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"a/{rel}",
                tofile=f"b/{rel}",
                lineterm="",
            )
        )
        diff_text = "\n".join(diff_lines)
        has_changes = bool(diff_lines)
        diff_line_count = diff_text.count("\n") + 1 if diff_text else 0
        large_patch = diff_line_count > self.max_diff_lines
        meta = self._infer_file_meta(rel, task)
        return {
            "ok": True,
            "mode": "patch_preview",
            "path": rel,
            "has_changes": has_changes,
            "diff": diff_text if has_changes else "Keine inhaltliche Aenderung erkannt.",
            "writes_files": False,
            "risk": meta["risk"],
            "reason": meta["reason"],
            "target_area": meta["target_area"],
            "confidence": meta["confidence"],
            "large_patch": large_patch,
            "blocked": bool(large_patch),
            "block_reason": "Patch überschreitet sichere Diff-Schwelle." if large_patch else "",
            "diff_line_count": diff_line_count,
        }

    def generate_patch(self, rel_path: str, current_content: str, proposed_content: str, task: str = "", context: str = "") -> dict:
        out = self._generate_single_patch(rel_path, current_content, proposed_content, task=task)
        if not out.get("ok"):
            return out
        out["task"] = str(task or "")
        out["context_hint"] = str(context or "")[:800]
        out["patch_plan"] = [
            {
                "file": out["path"],
                "target_area": out["target_area"],
                "planned_patch_summary": out["reason"],
                "risk": out["risk"],
                "confidence": out["confidence"],
                "has_changes": out["has_changes"],
                "blocked": out["blocked"],
            }
        ]
        return out

    def generate_patch_plan(self, entries: list[dict], task: str = "", context: str = "") -> dict:
        items = list(entries or [])
        if not items:
            return {"ok": False, "error": "entries fehlen."}
        file_plans = []
        blocked = False
        for e in items:
            path = str((e or {}).get("path") or "")
            current_content = str((e or {}).get("current_content") or "")
            proposed_content = str((e or {}).get("proposed_content") or "")
            one = self._generate_single_patch(path, current_content, proposed_content, task=task)
            if not one.get("ok"):
                return one
            blocked = blocked or bool(one.get("blocked"))
            file_plans.append(
                {
                    "file": one["path"],
                    "has_changes": one["has_changes"],
                    "diff": one["diff"],
                    "risk": one["risk"],
                    "reason": one["reason"],
                    "target_area": one["target_area"],
                    "confidence": one["confidence"],
                    "large_patch": one["large_patch"],
                    "blocked": one["blocked"],
                    "block_reason": one["block_reason"],
                }
            )
        return {
            "ok": True,
            "mode": "patch_plan",
            "task": str(task or ""),
            "context_hint": str(context or "")[:800],
            "files": [p["file"] for p in file_plans],
            "file_count": len(file_plans),
            "patch_plan": file_plans,
            "blocked": blocked,
            "writes_files": False,
        }


_INSTANCE: PatchGeneratorAgent | None = None


def get_instance(root: Path | None = None) -> PatchGeneratorAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PatchGeneratorAgent(root or Path("."))
    return _INSTANCE
