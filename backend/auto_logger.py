from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from uuid import uuid4


class AutoLogger:
    def __init__(self, db_path: str | Path | None = None):
        base_dir = Path(__file__).resolve().parent
        self.db_path = Path(db_path) if db_path else (base_dir / "data" / "passive_learning.json")
        self._lock = threading.Lock()

    def _ensure_db(self) -> dict:
        if not self.db_path.exists():
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "prompts": [],
                "results": [],
                "preferences": {"tech_weights": {}},
                "patterns": [],
                "mistakes": [],
                "learning_progress": [],
            }
            self.db_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
            return data
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception:
            return {
                "prompts": [],
                "results": [],
                "preferences": {"tech_weights": {}},
                "patterns": [],
                "mistakes": [],
                "learning_progress": [],
            }

    def _save_db(self, data: dict):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def auto_detect_type(self, prompt: str) -> str:
        text = str(prompt or "").lower()
        if any(k in text for k in ["bug", "fix", "error", "fehler"]):
            return "bugfix"
        if any(k in text for k in ["refactor", "umbau"]):
            return "refactor"
        if any(k in text for k in ["api", "backend", "endpoint"]):
            return "backend"
        if any(k in text for k in ["ui", "frontend", "css"]):
            return "frontend"
        return "general"

    def auto_estimate_difficulty(self, prompt: str) -> str:
        size = len(str(prompt or ""))
        text = str(prompt or "").lower()
        signals = sum(1 for k in ["architektur", "trade-off", "integration", "migration", "performance"] if k in text)
        if size > 500 or signals >= 3:
            return "high"
        if size > 150 or signals >= 1:
            return "medium"
        return "low"

    def log_prompt(self, prompt: str) -> str:
        with self._lock:
            data = self._ensure_db()
            prompt_id = uuid4().hex
            entry = {
                "id": prompt_id,
                "prompt": str(prompt or ""),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "problem_type": self.auto_detect_type(prompt),
                "difficulty": self.auto_estimate_difficulty(prompt),
            }
            data.setdefault("prompts", []).append(entry)
            self._save_db(data)
            return prompt_id

    def log_result(self, prompt_id: str, result: dict):
        with self._lock:
            data = self._ensure_db()
            generated_code = str((result or {}).get("generated_code") or "")
            improvements = (result or {}).get("improvements") or []
            entry = {
                "id": uuid4().hex,
                "prompt_id": str(prompt_id or ""),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "recommended_tech": str((result or {}).get("recommended_approach") or ""),
                "architecture": str((result or {}).get("architecture") or ""),
                "code_lines": len(generated_code.splitlines()),
                "improvements_count": len(improvements) if isinstance(improvements, list) else 0,
                "final": bool((result or {}).get("final")),
            }
            data.setdefault("results", []).append(entry)
            self._save_db(data)
