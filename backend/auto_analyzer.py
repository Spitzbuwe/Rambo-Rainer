from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


class AutoAnalyzer:
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

    def get_last_24h_data(self) -> dict:
        db = self._load()
        border = datetime.now() - timedelta(hours=24)

        def in_window(entry):
            try:
                return datetime.fromisoformat(str(entry.get("timestamp") or "")) >= border
            except Exception:
                return False

        return {
            "prompts": [p for p in db.get("prompts", []) if in_window(p)],
            "results": [r for r in db.get("results", []) if in_window(r)],
        }

    def find_common_types(self, recent_data: dict) -> dict:
        c = Counter(str(item.get("problem_type") or "unknown") for item in recent_data.get("prompts", []))
        return dict(c.most_common(10))

    def find_best_techs(self, recent_data: dict) -> dict:
        scores = defaultdict(lambda: {"ok": 0, "total": 0})
        for item in recent_data.get("results", []):
            tech = str(item.get("recommended_tech") or "unknown").strip() or "unknown"
            scores[tech]["total"] += 1
            if bool(item.get("final")):
                scores[tech]["ok"] += 1
        return {
            tech: (vals["ok"] / vals["total"] if vals["total"] else 0.0)
            for tech, vals in scores.items()
        }

    def find_patterns(self, recent_data: dict) -> list[dict]:
        prompts = {str(p.get("id")): p for p in recent_data.get("prompts", [])}
        patterns = []
        for r in recent_data.get("results", []):
            p = prompts.get(str(r.get("prompt_id") or ""))
            if not p:
                continue
            patterns.append({
                "problem_type": p.get("problem_type"),
                "tech": r.get("recommended_tech"),
                "architecture": r.get("architecture"),
                "success": bool(r.get("final")),
            })
        return patterns[-50:]

    def count_improvements(self, recent_data: dict) -> int:
        return int(sum(int(item.get("improvements_count") or 0) for item in recent_data.get("results", [])))

    def analyze_automatically(self) -> dict:
        recent_data = self.get_last_24h_data()
        return {
            "most_common_problems": self.find_common_types(recent_data),
            "best_performing_techs": self.find_best_techs(recent_data),
            "patterns": self.find_patterns(recent_data),
            "improvements_made": self.count_improvements(recent_data),
        }

    def increase_tech_weight(self, tech: str, by: float = 0.05):
        db = self._load()
        weights = db.setdefault("preferences", {}).setdefault("tech_weights", {})
        weights[tech] = float(weights.get(tech, 1.0)) + by
        self._save(db)

    def decrease_tech_weight(self, tech: str, by: float = 0.05):
        db = self._load()
        weights = db.setdefault("preferences", {}).setdefault("tech_weights", {})
        weights[tech] = max(0.1, float(weights.get(tech, 1.0)) - by)
        self._save(db)

    def auto_update_preferences(self, analysis: dict):
        for tech, success_rate in (analysis.get("best_performing_techs") or {}).items():
            db = self._load()
            weights = db.setdefault("preferences", {}).setdefault("tech_weights", {})
            if tech not in weights:
                weights[tech] = 1.0
                self._save(db)
            if float(success_rate) > 0.85:
                self.increase_tech_weight(tech)
            elif float(success_rate) < 0.40:
                self.decrease_tech_weight(tech)
