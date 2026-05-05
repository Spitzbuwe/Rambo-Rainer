"""Continual Learning — JSON unter .rainer_agent/, Aehnlichkeit, Few-Shot, Transfer."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(s: str) -> set[str]:
    return set(_TOKEN_RE.findall((s or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


class ContinualLearning:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.learning_dir = self.project_root / ".rainer_agent"
        self.learning_db = self.learning_dir / "learning.json"
        self.learnings: dict[str, Any] = self._load()
        self._embedding_model = None

    def _load(self) -> dict[str, Any]:
        if self.learning_db.exists():
            try:
                return json.loads(self.learning_db.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("learning.json defekt — neuer Stand")
        return {
            "task_patterns": {},
            "command_success_rates": {},
            "error_solutions": {},
            "best_practices": [],
            "model_preferences": {},
            "tasks": {},
            "patterns": {},
        }

    def _save(self) -> None:
        self.learning_dir.mkdir(parents=True, exist_ok=True)
        self.learning_db.write_text(
            json.dumps(self.learnings, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def learn_from_task(self, task: str, result: dict[str, Any], success: bool) -> None:
        pattern = self._pattern(task)
        tp = self.learnings.setdefault("task_patterns", {}).setdefault(
            pattern, {"success": 0, "total": 0}
        )
        tp["total"] += 1
        if success:
            tp["success"] += 1
        if not success and result.get("error"):
            self.learnings.setdefault("error_solutions", {})[str(result["error"])[:120]] = {
                "task": task[:200],
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        tid = hashlib.sha256(task.encode("utf-8", errors="replace")).hexdigest()[:16]
        rate = tp["success"] / tp["total"] if tp["total"] else 0.0
        self.learnings.setdefault("tasks", {})[tid] = {
            "task": task[:800],
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "solution": str(result.get("response", result.get("output", "")))[:2000],
            "success_rate": round(rate, 4),
            "pattern": pattern,
        }
        self._save()

    def _pattern(self, task: str) -> str:
        t = task.lower()
        if "python" in t:
            return "python"
        if "test" in t:
            return "testing"
        return "general"

    def _simple_text_search(self, task: str, top_k: int) -> list[dict[str, Any]]:
        qt = _tokens(task)
        scored: list[tuple[float, dict[str, Any]]] = []
        for _tid, info in self.learnings.get("tasks", {}).items():
            if not isinstance(info, dict):
                continue
            txt = str(info.get("task", ""))
            sim = _jaccard(qt, _tokens(txt))
            scored.append(
                (
                    sim,
                    {
                        "task": txt,
                        "similarity": sim,
                        "solution": info.get("solution", ""),
                        "success_rate": float(info.get("success_rate", 0.0)),
                    },
                )
            )
        scored.sort(key=lambda x: x[0], reverse=True)
        return [x[1] for x in scored[:top_k]]

    def similarity_search(self, task: str, top_k: int = 5) -> list[dict[str, Any]]:
        if os.getenv("RAINER_AGENT_DISABLE_ST", "").strip().lower() in ("1", "true", "yes", "on"):
            return self._simple_text_search(task, top_k)
        if self._embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                return self._simple_text_search(task, top_k)

        model = self._embedding_model
        query_emb = model.encode(task, convert_to_numpy=True)

        def _cos(a, b) -> float:
            na = float((a * a).sum() ** 0.5) or 1.0
            nb = float((b * b).sum() ** 0.5) or 1.0
            return float((a @ b) / (na * nb))

        results: list[dict[str, Any]] = []
        for _tid, info in self.learnings.get("tasks", {}).items():
            if not isinstance(info, dict):
                continue
            learned = str(info.get("task", ""))
            if not learned.strip():
                continue
            emb = model.encode(learned, convert_to_numpy=True)
            sim = _cos(query_emb, emb)
            results.append(
                {
                    "task": learned,
                    "similarity": sim,
                    "solution": info.get("solution", ""),
                    "success_rate": float(info.get("success_rate", 0.0)),
                }
            )
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def few_shot_learning(self, new_task: str, num_examples: int = 5) -> dict[str, Any]:
        similar = self.similarity_search(new_task, top_k=num_examples)
        if not similar:
            return {"error": "No similar examples found", "similar_examples": []}
        patterns = [
            {
                "task": s["task"],
                "solution": s.get("solution", ""),
                "success_rate": s.get("success_rate", 0.0),
            }
            for s in similar
        ]
        rule = self._generalize_patterns(patterns, new_task)
        conf = min(1.0, len(similar) / max(1, num_examples))
        return {
            "similar_examples": similar,
            "generalized_rule": rule,
            "confidence": conf,
        }

    def _extract_keywords(self, text: str) -> list[str]:
        stop = {"the", "and", "for", "with", "from", "this", "that", "eine", "einen", "der", "die", "das"}
        words = [w for w in _TOKEN_RE.findall(text.lower()) if len(w) > 2 and w not in stop]
        freq: dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        return [k for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:12]]

    @staticmethod
    def _find_common_steps(solutions: list[str]) -> list[str]:
        if not solutions:
            return []
        tok_sets = [_tokens(s) for s in solutions if s]
        if not tok_sets:
            return []
        common = set.intersection(*tok_sets)
        return sorted(common)[:20]

    def _generalize_patterns(self, patterns: list[dict[str, Any]], new_task: str) -> dict[str, Any]:
        keywords = self._extract_keywords(new_task)
        sols = [str(p.get("solution", "")) for p in patterns]
        steps = self._find_common_steps(sols)
        rates = [float(p.get("success_rate", 0.0)) for p in patterns]
        exp = sum(rates) / len(rates) if rates else 0.0
        return {
            "for_tasks_with_keywords": keywords,
            "apply_these_steps": steps,
            "expected_success_rate": round(exp, 4),
        }

    def generalization(self, patterns: list[dict[str, Any]], new_task: str) -> dict[str, Any]:
        return self._generalize_patterns(patterns, new_task)

    def transfer_learning(self, source_project: Path, target_project: Path) -> dict[str, Any]:
        src = ContinualLearning(source_project)
        tgt = ContinualLearning(target_project)
        source_learning = src.learnings
        transferred: dict[str, Any] = {"patterns": [], "rules": [], "best_practices": []}
        for pattern, stats in source_learning.get("patterns", {}).items():
            if isinstance(stats, dict) and self._is_general_pattern(str(pattern)):
                transferred["patterns"].append(
                    {"pattern": str(pattern), "success_rate": stats.get("success_rate", 0.0)}
                )
        for practice in source_learning.get("best_practices", []):
            if self._is_transferable(practice):
                transferred["best_practices"].append(practice)
        self._merge_into(tgt, transferred)
        tgt._save()
        return {
            "transferred": transferred,
            "source": str(Path(source_project).resolve()),
            "target": str(Path(target_project).resolve()),
        }

    @staticmethod
    def _is_general_pattern(pattern: str) -> bool:
        p = pattern.lower()
        return len(p) < 80 and not p.startswith("/")

    @staticmethod
    def _is_transferable(practice: Any) -> bool:
        if isinstance(practice, str):
            return len(practice) < 500
        if isinstance(practice, dict):
            return "tip" in practice or "text" in practice
        return False

    def _merge_into(self, target: ContinualLearning, transferred: dict[str, Any]) -> None:
        for p in transferred.get("patterns", []):
            key = str(p.get("pattern", ""))[:200]
            if not key:
                continue
            target.learnings.setdefault("patterns", {})[key] = {
                "success_rate": p.get("success_rate", 0.0),
                "imported": datetime.now(timezone.utc).isoformat(),
            }
        bp = target.learnings.setdefault("best_practices", [])
        for item in transferred.get("best_practices", []):
            if item not in bp:
                bp.append(item)

    def learning_curve_tracking(self) -> dict[str, Any]:
        tasks = self.learnings.get("tasks", {})
        items: list[tuple[str, dict[str, Any]]] = []
        for tid, info in tasks.items():
            if isinstance(info, dict):
                items.append((str(info.get("timestamp", "")), info))
        items.sort(key=lambda x: x[0])
        window_size = 10
        success_rates: list[float] = []
        for i in range(0, len(items), window_size):
            window = items[i : i + window_size]
            if not window:
                continue
            success = sum(1 for _, inf in window if inf.get("success"))
            success_rates.append(success / len(window))
        trend = "increasing" if self._is_improving(success_rates) else "plateauing"
        return {
            "total_tasks_learned": len(tasks),
            "success_rate_over_time": success_rates,
            "improvement_trend": trend,
            "current_success_rate": success_rates[-1] if success_rates else 0.0,
        }

    @staticmethod
    def _is_improving(rates: list[float]) -> bool:
        if len(rates) < 2:
            return False
        half = len(rates) // 2
        a = sum(rates[:half]) / half if half else 0.0
        b = sum(rates[half:]) / (len(rates) - half) if len(rates) > half else 0.0
        return b > a + 0.05

    def knowledge_consolidation(self) -> dict[str, Any]:
        tp = self.learnings.get("task_patterns", {})
        summary: list[dict[str, Any]] = []
        for name, stats in tp.items():
            if isinstance(stats, dict) and stats.get("total", 0) > 0:
                sr = stats.get("success", 0) / stats["total"]
                summary.append({"pattern": name, "success_rate": round(sr, 4), "n": stats["total"]})
        summary.sort(key=lambda x: -x["success_rate"])
        self.learnings["consolidated_summary"] = summary[:50]
        self._save()
        return {"summary": summary[:20], "stored": True}

    def health(self) -> dict[str, Any]:
        return {"module": "agent_continual_learning", "ok": True}


continual_learning = ContinualLearning()
__all__ = ["ContinualLearning", "continual_learning"]
