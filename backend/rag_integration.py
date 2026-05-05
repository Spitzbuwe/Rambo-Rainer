from __future__ import annotations

import json
from pathlib import Path


class RAGIntegration:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def _load(self) -> dict:
        if not self.db_path.exists():
            return {"patterns": [], "prompts": [], "results": []}
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception:
            return {"patterns": [], "prompts": [], "results": []}

    def retrieve_similar_context(self, prompt: str, top_k: int = 3) -> list[dict]:
        text = str(prompt or "").lower()
        db = self._load()
        scored = []
        for item in db.get("patterns", []):
            problem_type = str(item.get("problem_type") or "").lower()
            solution = str(item.get("solution") or "").lower()
            score = 0
            if problem_type and problem_type in text:
                score += 2
            for token in solution.split():
                if token and token in text:
                    score += 1
            if score > 0:
                scored.append((score, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [i[1] for i in scored[:top_k]]

    def format_context(self, items: list[dict]) -> str:
        if not items:
            return ""
        lines = ["RAG-Kontext (aehnliche historische Patterns):"]
        for idx, item in enumerate(items, 1):
            lines.append(
                f"{idx}. problem_type={item.get('problem_type')} | solution={item.get('solution')} | success={item.get('success')}"
            )
        return "\n".join(lines)
