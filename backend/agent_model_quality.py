from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_model_router import get_instance as get_model_router

COMPLEX_INDICATORS = [
    "architektur",
    "architecture",
    "refactor",
    "performance",
    "security",
    "parallel",
    "analyze",
    "analyse",
    "tradeoff",
]
SIMPLE_INDICATORS = ["rename", "format", "fix typo", "comment", "was ist", "what is"]


def analyze_complexity(prompt: str) -> dict[str, Any]:
    text = (prompt or "").lower()
    wc = len((prompt or "").split())
    complex_score = sum(1 for k in COMPLEX_INDICATORS if k in text) + (2 if wc > 100 else 0)
    simple_score = sum(1 for k in SIMPLE_INDICATORS if k in text) + (1 if wc < 20 else 0)
    if complex_score >= 2:
        return {"complexity": "high", "recommended_provider": "anthropic_api", "reason": "complex_task"}
    if simple_score >= 1:
        return {"complexity": "low", "recommended_provider": "ollama_local", "reason": "simple_task"}
    return {"complexity": "medium", "recommended_provider": "ollama_local", "reason": "default_local_first"}


def evaluate_response_quality(prompt: str, response: str, task_type: str = "generic") -> dict[str, Any]:
    score = 50
    txt = (response or "").strip()
    if len(txt) < 20:
        score -= 30
    elif len(txt) > 100:
        score += 10
    if task_type in ("coding", "patch") and ("```" in txt or "def " in txt or "function " in txt):
        score += 15
    if "\n" in txt:
        score += 5
    score = max(0, min(100, score))
    return {"score": score, "quality": ("high" if score >= 70 else "medium" if score >= 40 else "low"), "should_escalate": score < 40}


@dataclass
class QualityResult:
    text: str
    provider: str
    model: str
    latency_ms: int
    quality_score: int
    complexity: str
    escalated: bool = False
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "quality_score": self.quality_score,
            "complexity": self.complexity,
            "escalated": self.escalated,
            "cached": self.cached,
        }


class QualityRouter:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.router = get_model_router(self.project_root)
        self._cache: dict[str, QualityResult] = {}
        self._stats: list[dict[str, Any]] = []

    def _cache_key(self, prompt: str, task_type: str) -> str:
        return hashlib.md5(f"{task_type}:{prompt[:200]}".encode("utf-8", errors="ignore")).hexdigest()

    def _simulate_text(self, prompt: str, selected_model: str, task_type: str) -> str:
        p = (prompt or "").strip()
        base = f"[{selected_model}] {p[:240]}".strip()
        if task_type in ("coding", "patch"):
            return base + "\n```python\n# suggested patch outline\npass\n```"
        return base + "\n- structured response"

    def route_with_quality(
        self,
        prompt: str,
        task_type: str = "generic",
        min_quality: int = 40,
        use_cache: bool = True,
        allow_external: bool = False,
    ) -> QualityResult:
        key = self._cache_key(prompt, task_type)
        if use_cache and key in self._cache:
            r = self._cache[key]
            r.cached = True
            return r

        complexity = analyze_complexity(prompt)
        start = time.time()
        plan = self.router.build_route_plan(prompt)
        latency_ms = int((time.time() - start) * 1000)
        selected_model = str(plan.get("selected_model") or "qwen2.5-coder:7b")
        selected_provider = str(plan.get("selected_provider") or "ollama_local")
        text = self._simulate_text(prompt, selected_model, task_type)
        quality = evaluate_response_quality(prompt, text, task_type)

        escalated = False
        if quality["score"] < int(min_quality) and selected_provider == "ollama_local" and allow_external:
            # Safe escalation planning only; no external call.
            escalated = True
            selected_provider = "anthropic_api"
            selected_model = "claude-3-5-sonnet-latest"
            text = self._simulate_text(prompt, selected_model, task_type)
            quality = evaluate_response_quality(prompt, text, task_type)

        out = QualityResult(
            text=text,
            provider=selected_provider,
            model=selected_model,
            latency_ms=latency_ms,
            quality_score=int(quality["score"]),
            complexity=str(complexity["complexity"]),
            escalated=escalated,
            cached=False,
        )
        self._cache[key] = out
        self._stats.append(
            {
                "provider": out.provider,
                "model": out.model,
                "quality_score": out.quality_score,
                "latency_ms": out.latency_ms,
                "complexity": out.complexity,
                "escalated": out.escalated,
                "allow_external": bool(allow_external),
            }
        )
        self._stats = self._stats[-300:]
        return out

    def quality_stats(self) -> dict[str, Any]:
        rows = list(self._stats)
        avg_quality = (sum(int(r.get("quality_score") or 0) for r in rows) / len(rows)) if rows else 0.0
        return {"ok": True, "count": len(rows), "avg_quality": round(avg_quality, 2), "recent": rows[-20:], "cache_size": len(self._cache)}


_INSTANCE: QualityRouter | None = None


def get_instance(project_root: Path | str | None = None) -> QualityRouter:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = QualityRouter(project_root)
    return _INSTANCE
