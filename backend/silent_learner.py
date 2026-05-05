from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class SilentLearner:
    def __init__(self, db_path: str | Path | None = None):
        base_dir = Path(__file__).resolve().parent
        self.db_path = Path(db_path) if db_path else (base_dir / "data" / "passive_learning.json")

    def _load(self) -> dict:
        if not self.db_path.exists():
            return {
                "prompts": [],
                "results": [],
                "preferences": {"tech_weights": {}},
                "patterns": [],
                "mistakes": [],
                "learning_progress": [],
            }
        try:
            return json.loads(self.db_path.read_text(encoding="utf-8"))
        except Exception:
            return {"prompts": [], "results": [], "preferences": {"tech_weights": {}}, "patterns": [], "mistakes": [], "learning_progress": []}

    def _save(self, data: dict):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def track_decision(self, tech_choice: str, success: bool):
        db = self._load()
        db.setdefault("learning_progress", []).append({
            "kind": "tech_decision",
            "value": str(tech_choice or "unknown"),
            "success": bool(success),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(db)

    def track_architecture(self, arch_choice: str, success: bool):
        db = self._load()
        db.setdefault("learning_progress", []).append({
            "kind": "architecture",
            "value": str(arch_choice or "unknown"),
            "success": bool(success),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(db)

    def track_code_quality(self, code: str, test_results: dict | None = None):
        db = self._load()
        db.setdefault("learning_progress", []).append({
            "kind": "code_quality",
            "code_lines": len(str(code or "").splitlines()),
            "test_results": test_results or {},
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(db)

    def was_successful(self, result: dict) -> bool:
        return bool((result or {}).get("final")) and bool((result or {}).get("stop_continue"))

    def remember_pattern(self, problem_type: str, solution: str, success: bool = True):
        db = self._load()
        db.setdefault("patterns", []).append({
            "problem_type": str(problem_type or "general"),
            "solution": str(solution or "unknown"),
            "success": bool(success),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(db)

    def remember_mistake(self, problem_type: str, solution: str, reason: str):
        db = self._load()
        db.setdefault("mistakes", []).append({
            "problem_type": str(problem_type or "general"),
            "solution": str(solution or "unknown"),
            "reason": str(reason or "unspecified"),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
        self._save(db)

    def get_all_patterns(self) -> list[dict]:
        return self._load().get("patterns", [])

    def rank_by_success(self, patterns: list[dict]) -> list[dict]:
        return sorted(patterns or [], key=lambda p: (1 if p.get("success") else 0), reverse=True)

    def update_decision_weights(self, best_patterns: list[dict]):
        db = self._load()
        weights = db.setdefault("preferences", {}).setdefault("tech_weights", {})
        for p in (best_patterns or [])[:20]:
            key = str(p.get("solution") or "unknown")
            weights[key] = float(weights.get(key, 1.0)) + (0.05 if p.get("success") else -0.02)
            if weights[key] < 0.1:
                weights[key] = 0.1
        self._save(db)

    def learn_from_current_session(self, result: dict):
        result = result or {}
        tech_choice = str(result.get("recommended_approach") or "unknown")
        arch_choice = str(result.get("architecture") or "unknown")
        code = str(result.get("generated_code") or "")
        success = self.was_successful(result)
        self.track_decision(tech_choice, success)
        self.track_architecture(arch_choice, success)
        self.track_code_quality(code, {"final": bool(result.get("final")), "stop_continue": bool(result.get("stop_continue"))})

        problem_type = str(((result.get("analysis") or {}).get("actual_problem")) or "general")
        if success:
            self.remember_pattern(problem_type=problem_type, solution=tech_choice, success=True)
        else:
            self.remember_mistake(problem_type=problem_type, solution=tech_choice, reason="Run nicht final abgeschlossen")

    def evolve_silently(self):
        all_patterns = self.get_all_patterns()
        best_patterns = self.rank_by_success(all_patterns)
        self.update_decision_weights(best_patterns)
