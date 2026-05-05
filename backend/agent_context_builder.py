from __future__ import annotations

import re
from pathlib import Path

from agent_file_reader import FileReaderAgent


class ContextBuilderAgent:
    def __init__(self, reader: FileReaderAgent):
        self.reader = reader

    def _extract_focus_snippet(self, content: str, task: str, max_chars: int) -> tuple[str, str]:
        text = str(content or "")
        if not text:
            return "", "empty_file"
        task_tokens = [t for t in re.split(r"[^a-zA-Z0-9_]+", str(task or "").lower()) if len(t) >= 3]
        lines = text.splitlines()
        hit_idx = None
        for i, line in enumerate(lines):
            ll = line.lower()
            if any(tok in ll for tok in task_tokens):
                hit_idx = i
                break
        if hit_idx is None:
            # fallback: first meaningful code window
            snippet = text[: max(120, int(max_chars))]
            return snippet, "default_window"
        start = max(0, hit_idx - 6)
        end = min(len(lines), hit_idx + 10)
        snippet = "\n".join(lines[start:end])[: max(120, int(max_chars))]
        return snippet, f"task_hit_line_{hit_idx+1}"

    def build_context(
        self,
        task: str,
        *,
        limit: int = 4,
        max_chars_per_file: int = 2500,
        planner_steps: list[dict] | None = None,
        total_budget_chars: int | None = None,
    ) -> dict:
        query = str(task or "").strip()
        if not query:
            return {"ok": False, "error": "task fehlt."}
        lim = max(1, int(limit))
        per_file = max(500, int(max_chars_per_file))
        total_budget = max(per_file, int(total_budget_chars or (per_file * lim)))
        raw = self.reader.read_relevant_files(query, limit=lim, max_chars=per_file)
        files = list(raw.get("files") or [])
        pre_paths = list(raw.get("candidates") or [])
        selected_set = {str(f.get("path") or "") for f in files if f.get("path")}
        not_selected = []
        for p in pre_paths:
            path = str(p or "")
            if not path or path in selected_set:
                continue
            reason = "limit_reached_or_lower_relevance"
            if any(path == str(x.get("path") or "") for x in files):
                reason = "duplicate"
            not_selected.append({"path": path, "reason": reason})

        # Remove duplicate blocks by normalized content hash and enforce global budget
        used_budget = 0
        seen_signatures = set()
        context_blocks = []
        selected_files = []
        extraction_notes = []
        for item in files:
            path = str(item.get("path") or "")
            content = str(item.get("content") or "")
            if not path:
                continue
            snippet_budget = min(per_file, max(120, total_budget - used_budget))
            if snippet_budget <= 0:
                not_selected.append({"path": path, "reason": "global_budget_exhausted"})
                continue
            snippet, extraction_mode = self._extract_focus_snippet(content, query, snippet_budget)
            sig = (path.lower(), snippet.strip()[:240].lower())
            if sig in seen_signatures:
                not_selected.append({"path": path, "reason": "duplicate_context_block_removed"})
                continue
            seen_signatures.add(sig)
            block = f"[FILE] {path}\n{snippet}"
            context_blocks.append(block)
            selected_files.append(path)
            used_budget += len(snippet)
            extraction_notes.append({"path": path, "extraction_mode": extraction_mode, "chars": len(snippet)})

        planner = list(planner_steps or [])
        planner_labels = [str((s or {}).get("label") or "") for s in planner if str((s or {}).get("label") or "").strip()]
        return {
            "ok": True,
            "mode": "task_context_pro",
            "task": query,
            "selected_files": selected_files,
            "file_count": len(selected_files),
            "context_blocks": context_blocks,
            "context_text": "\n\n".join(context_blocks),
            "planner_steps_used": planner_labels,
            "total_budget_chars": total_budget,
            "used_budget_chars": used_budget,
            "dropped_duplicate_blocks": len([x for x in not_selected if x.get("reason") == "duplicate_context_block_removed"]),
            "not_selected_files": not_selected,
            "extraction_notes": extraction_notes,
            "notes": "Kontext wurde selektiv, dedupliziert und budgetiert aufgebaut.",
            "reads_all_files": False,
        }

    def health(self) -> dict:
        return {"ok": True, "mode": "task_context", "reads_all_files": False}


_INSTANCE: ContextBuilderAgent | None = None


def get_instance(root: Path | None = None, skip_dirs: set[str] | None = None) -> ContextBuilderAgent:
    global _INSTANCE
    if _INSTANCE is None:
        reader = FileReaderAgent(root or Path("."), skip_dirs=skip_dirs or set())
        _INSTANCE = ContextBuilderAgent(reader)
    return _INSTANCE
