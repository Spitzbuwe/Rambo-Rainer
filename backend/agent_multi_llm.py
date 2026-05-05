"""
Multi-LLM Router — Komplexitaet, Modellwahl, Ensemble, Fallback, Metriken.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelConfig:
    name: str
    complexity_min: int
    complexity_max: int
    timeout: int
    strengths: tuple[str, ...]


MODELS: dict[str, ModelConfig] = {
    "deepseek-coder:33b": ModelConfig(
        "deepseek-coder:33b", 50, 100, 300, ("code", "architecture", "analysis")
    ),
    "mistral:latest": ModelConfig("mistral:latest", 0, 60, 60, ("speed", "reasoning")),
    "neural-chat:latest": ModelConfig(
        "neural-chat:latest", 30, 80, 120, ("chat", "explanation", "dialogue")
    ),
    "llama2:latest": ModelConfig("llama2:latest", 20, 90, 180, ("general", "coding")),
    "codellama:latest": ModelConfig(
        "codellama:latest", 40, 100, 240, ("code", "debugging")
    ),
}

_BAD_QUALITY_MARKERS = (
    "i don't know",
    "i do not know",
    "unable to answer",
    "cannot answer",
    "no information available",
    "error:",
    "failed to",
)


class MultiLLMRouter:
    """Router mit Ensemble, Fallback-Kette, Caching und Health."""

    def __init__(self) -> None:
        self.models = MODELS
        self.success_rates: dict[str, float] = {m: 0.8 for m in self.models}
        self.health_status: dict[str, bool] = {m: True for m in self.models}
        self.performance_cache: dict[str, dict[str, dict[str, float]]] = {}
        self.response_cache: dict[str, dict[str, Any]] = {}
        self._last_metrics: dict[str, Any] = {}
        self._session = requests.Session()
        self._ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        # Tests: monkeypatch auf Callable[[str, str], str] oder dict
        self._query_fn: Callable[[str, str], Any] | None = None

    @staticmethod
    def task_hash(task: str) -> str:
        return hashlib.sha256(task.strip().encode("utf-8")).hexdigest()[:32]

    def calculate_task_complexity(self, task: str) -> int:
        t = task.lower()
        c = 30
        if any(k in t for k in ("hello", "print", "echo")):
            c = min(30, c)
        if any(k in t for k in ("api", "database", "algorithm")):
            c = max(c, 50)
        if any(k in t for k in ("architecture", "security", "distributed")):
            c = max(c, 80)
        c += min(20, len(task.split()) // 5)
        return max(0, min(100, c))

    def select_best_model(self, task: str, preferred: list[str] | None = None) -> str:
        cx = self.calculate_task_complexity(task)
        suitable = [
            n for n, cfg in self.models.items() if cfg.complexity_min <= cx <= cfg.complexity_max
        ] or list(self.models.keys())
        if preferred:
            best, score = suitable[0], -1
            for n in suitable:
                cfg = self.models[n]
                sc = sum(1 for q in preferred if q in cfg.strengths)
                if sc > score:
                    best, score = n, sc
            return best
        return max(suitable, key=lambda m: self.success_rates.get(m, 0.5))

    def adaptive_model_selection(self, task: str) -> dict[str, Any]:
        primary = self.select_best_model(task)
        alt = sorted(
            self.models.keys(),
            key=lambda m: self.success_rates.get(m, 0.5),
            reverse=True,
        )[:3]
        return {
            "primary": primary,
            "alternates": [m for m in alt if m != primary][:2],
            "complexity": self.calculate_task_complexity(task),
            "success_rates": dict(self.success_rates),
        }

    def update_success_rate(self, model_name: str, success: bool) -> None:
        if model_name not in self.success_rates:
            return
        cur = self.success_rates[model_name]
        self.success_rates[model_name] = 0.9 * cur + 0.1 * (1.0 if success else 0.0)

    def response_quality_assessment(self, response: str) -> dict[str, Any]:
        text = (response or "").strip()
        if len(text) < 10:
            return {"ok": False, "reason": "too_short", "score": 0.0}
        low = text.lower()
        if any(b in low for b in _BAD_QUALITY_MARKERS):
            return {"ok": False, "reason": "weak_or_error_phrase", "score": 0.2}
        score = min(1.0, 0.4 + min(0.6, len(text) / 4000.0))
        return {"ok": True, "reason": "heuristic_ok", "score": score}

    def caching_for_identical_tasks(self, task: str) -> dict[str, Any] | None:
        return self.response_cache.get(self.task_hash(task))

    def set_response_cache(self, task: str, payload: dict[str, Any]) -> None:
        self.response_cache[self.task_hash(task)] = payload

    def model_health_check(self, model: str) -> dict[str, Any]:
        if self._query_fn is not None:
            return {"ok": self.health_status.get(model, True), "model": model, "source": "test_hook"}
        try:
            r = self._session.get(f"{self._ollama_url}/api/tags", timeout=3)
            r.raise_for_status()
            names = [m.get("name") for m in (r.json() or {}).get("models") or [] if isinstance(m, dict)]
            ok = any(
                n == model or (isinstance(n, str) and n.startswith(model.split(":")[0]))
                for n in names
                if n
            )
            self.health_status[model] = ok
            return {"ok": ok, "model": model, "ollama_reachable": True}
        except (requests.RequestException, OSError, ValueError, TypeError) as e:
            logger.warning("model_health_check: %s", e)
            return {"ok": False, "model": model, "error": str(e), "ollama_reachable": False}

    def performance_metrics(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "success_rates": dict(self.success_rates),
            "health": dict(self.health_status),
            "cached_tasks": len(self.response_cache),
            "performance_entries": sum(len(v) for v in self.performance_cache.values()),
        }
        self._last_metrics = out
        return out

    def _select_top_models(self, task: str, top_n: int) -> list[str]:
        ranked = sorted(self.models.keys(), key=lambda m: self.success_rates.get(m, 0.5), reverse=True)
        primary = self.select_best_model(task)
        order = [primary] + [m for m in ranked if m != primary]
        return order[: max(1, top_n)]

    def _query_model(self, model: str, task: str, timeout: int) -> dict[str, Any]:
        if self._query_fn is not None:
            raw = self._query_fn(model, task)
            if isinstance(raw, dict):
                return raw
            return {"success": True, "response": str(raw), "model": model, "elapsed_seconds": 0.01}
        return self._ollama_generate(model, task, timeout)

    def _ollama_generate(self, model: str, task: str, timeout: int) -> dict[str, Any]:
        start = time.time()
        try:
            r = self._session.post(
                f"{self._ollama_url}/api/generate",
                json={
                    "model": model,
                    "system": "",
                    "prompt": json.dumps({"model": model, "input": task}, ensure_ascii=False),
                    "stream": False,
                    "temperature": 0.45,
                },
                timeout=max(5, timeout),
            )
            elapsed = time.time() - start
            r.raise_for_status()
            payload = r.json() or {}
            text = str(payload.get("response") or "").strip()
            return {
                "success": True,
                "response": text,
                "model": model,
                "elapsed_seconds": elapsed,
            }
        except (requests.RequestException, OSError, ValueError, TypeError) as e:
            elapsed = time.time() - start
            self.health_status[model] = False
            return {"success": False, "error": str(e), "model": model, "elapsed_seconds": elapsed}

    def _query_model_with_timeout(self, model: str, task: str, timeout: int = 60) -> str:
        cfg = self.models.get(model)
        t = timeout if cfg is None else min(timeout, cfg.timeout)
        res = self._query_model(model, task, t)
        if not res.get("success"):
            raise RuntimeError(res.get("error", "unknown"))
        return str(res.get("response") or "")

    def _record_performance(self, task: str, model: str, response: str, elapsed: float) -> None:
        th = self.task_hash(task)
        q = self.response_quality_assessment(response).get("score", 0.0)
        self.performance_cache.setdefault(th, {})[model] = {"elapsed": elapsed, "quality": float(q)}

    @staticmethod
    def _consensus_voting(responses: dict[str, str]) -> str:
        nonempty = {k: v for k, v in responses.items() if (v or "").strip()}
        if not nonempty:
            return ""
        return max(nonempty.items(), key=lambda x: len(x[1]))[1]

    @staticmethod
    def _calculate_confidence(responses: dict[str, str]) -> float:
        if not responses:
            return 0.0
        lengths = [len(r) for r in responses.values() if r]
        if not lengths:
            return 0.0
        avg_length = sum(lengths) / len(lengths)
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)
        confidence = 1.0 - (variance / (avg_length**2 + 1))
        return max(0.0, min(1.0, confidence))

    def ensemble_prediction(self, task: str, top_n: int = 3) -> dict[str, Any]:
        cached = self.caching_for_identical_tasks(task)
        if cached and cached.get("consensus"):
            return {**cached, "cache_hit": True}
        best_models = self._select_top_models(task, top_n)
        responses: dict[str, str] = {}
        raw_meta: dict[str, dict[str, Any]] = {}

        def run_one(m: str) -> tuple[str, str, dict[str, Any]]:
            cfg = self.models[m]
            res = self._query_model(m, task, cfg.timeout)
            return m, str(res.get("response") or ""), res

        with ThreadPoolExecutor(max_workers=min(4, len(best_models))) as ex:
            futures = {ex.submit(run_one, m): m for m in best_models}
            for fut in as_completed(futures):
                model, text, res = fut.result()
                responses[model] = text
                raw_meta[model] = res

        consensus = self._consensus_voting(responses)
        conf = self._calculate_confidence(responses)
        for model, text in responses.items():
            meta = raw_meta.get(model) or {}
            self._record_performance(task, model, text, float(meta.get("elapsed_seconds") or 0.0))
        payload = {
            "success": bool(consensus.strip()),
            "consensus": consensus,
            "all_responses": responses,
            "confidence": conf,
            "models_used": list(responses.keys()),
            "cache_hit": False,
        }
        if consensus.strip():
            self.set_response_cache(task, payload)
        return payload

    def fallback_chain(self, task: str, primary_model: str | None = None) -> dict[str, Any]:
        primary = primary_model or self.select_best_model(task)
        fallback_order: list[str] = []
        for m in [primary, *self.models.keys()]:
            if m not in fallback_order:
                fallback_order.append(m)
        last_error: str | None = None
        for model in fallback_order:
            if not self.health_status.get(model, True):
                continue
            try:
                cfg = self.models[model]
                text = self._query_model_with_timeout(model, task, timeout=min(90, cfg.timeout))
                qa = self.response_quality_assessment(text)
                if qa.get("ok"):
                    self.update_success_rate(model, True)
                    return {"success": True, "model": model, "response": text, "quality": qa}
            except Exception as e:
                last_error = str(e)
                self.update_success_rate(model, False)
                continue
        return {
            "success": False,
            "error": f"All models failed: {last_error}",
            "tried_models": fallback_order,
        }

    def health(self) -> dict[str, Any]:
        return {"module": "agent_multi_llm", "ok": True, "models": list(self.models.keys())}


multi_llm_router = MultiLLMRouter()
__all__ = [
    "MultiLLMRouter",
    "multi_llm_router",
    "MODELS",
    "ModelConfig",
]
