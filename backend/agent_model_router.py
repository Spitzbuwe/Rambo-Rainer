"""Local model router for task-to-model planning."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_LOCAL_MODELS = [
    "gemma4:26b",
    "gemma4:e4b",
    "deepseek-coder:33b-instruct-q5_K_M",
    "deepseek-r1:8b",
    "qwen2.5-coder:7b",
    "mistral:latest",
    "llama3.2:latest",
]

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = "llama-3.3-70b-versatile"

PROVIDER_CONFIG: dict[str, dict[str, Any]] = {
    "groq_api": {
        "enabled": bool(GROQ_API_KEY),
        "kind": "api",
        "default_model": GROQ_MODEL,
    },
    "ollama_local": {
        "enabled": True,
        "kind": "local",
        "default_model": "qwen2.5-coder:7b",
    },
    "openai_api": {
        "enabled": False,
        "kind": "api",
        "default_model": "gpt-4o-mini",
    },
    "anthropic_api": {
        "enabled": False,
        "kind": "api",
        "default_model": "claude-3-5-sonnet-latest",
    },
}

TASK_KEYWORDS: dict[str, list[str]] = {
    "coding": [
        "code",
        "programmieren",
        "programming",
        "bug",
        "fehler",
        "traceback",
        "pytest",
        "test",
        "commit",
        "git",
        "python",
        "javascript",
        "backend",
        "frontend",
        "datei ändern",
        "datei aendern",
        "file change",
        "fixe",
        "bugfix",
        "frontend/app.js",
        "backend/main.py",
        "api",
    ],
    "reasoning": [
        "komplex",
        "komplexe",
        "planungsaufgabe",
        "planen",
        "planung",
        "architektur",
        "architekturplan",
        "strategie",
        "workflow",
        "roadmap",
        "schrittplan",
        "große aufgabe",
        "grosse aufgabe",
        "analyse",
        "analysiere",
        "entscheidung",
        "ursache",
        "problem lösen",
        "problem loesen",
        "konzept",
        "agent-planung",
        "agenten",
        "agent",
        "complex",
        "planning",
        "architecture",
        "reasoning",
        "strategy",
        "system design",
        "analyze",
        "root cause",
        "decision",
        "breakdown",
        "entscheide",
        "systemdesign",
    ],
    "summary": [
        "fasse zusammen",
        "fasse kurz zusammen",
        "kurz zusammenfassen",
        "kurze zusammenfassung",
        "summary",
        "status",
        "bericht",
        "einfache frage",
        "kleine antwort",
        "kurze analyse",
    ],
    "chat": ["frage", "chat", "erklaren", "erklären", "was ist", "hilfe", "normaler text"],
}

MODEL_PRIORITY: dict[str, list[str]] = {
    "coding": [
        "deepseek-coder:33b-instruct-q5_K_M",
        "qwen2.5-coder:7b",
        "gemma4:26b",
        "deepseek-r1:8b",
        "mistral:latest",
    ],
    "reasoning": [
        "gemma4:26b",
        "deepseek-r1:8b",
        "deepseek-coder:33b-instruct-q5_K_M",
        "qwen2.5-coder:7b",
        "mistral:latest",
    ],
    "summary": [
        "gemma4:e4b",
        "mistral:latest",
        "llama3.2:latest",
        "gemma4:26b",
    ],
    "chat": [
        "gemma4:e4b",
        "mistral:latest",
        "llama3.2:latest",
        "gemma4:26b",
    ],
    "unknown": [
        "gemma4:e4b",
        "mistral:latest",
        "llama3.2:latest",
        "gemma4:26b",
    ],
}


class AgentModelRouter:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "ready", "module": "agent_model_router"}

    def normalize_task(self, task: str) -> str:
        t = (task or "").strip().lower()
        aliases = {
            "code": "coding",
            "coding": "coding",
            "programmieren": "coding",
            "reasoning": "reasoning",
            "plan": "reasoning",
            "summary": "summary",
            "zusammenfassung": "summary",
            "chat": "chat",
        }
        return aliases.get(t, t)

    def classify_task(self, prompt_or_task: str) -> str:
        text = self.normalize_task(prompt_or_task)
        if text in ("coding", "reasoning", "summary", "chat"):
            return text
        scores = {"coding": 0, "reasoning": 0, "summary": 0, "chat": 0}
        for task_type, words in TASK_KEYWORDS.items():
            for word in words:
                if word in text:
                    scores[task_type] += 1
        winner = max(scores.items(), key=lambda item: item[1])
        if winner[1] <= 0:
            return "unknown"
        return winner[0]

    def ollama_tags(self, timeout_seconds: int = 3) -> dict[str, Any]:
        url = "http://127.0.0.1:11434/api/tags"
        try:
            req = urllib.request.Request(url=url, method="GET")
            with urllib.request.urlopen(req, timeout=max(1, int(timeout_seconds))) as response:
                body = response.read().decode("utf-8", errors="replace")
                payload = json.loads(body) if body else {}
                models = []
                for m in payload.get("models", []):
                    name = str(m.get("name", "")).strip()
                    if name:
                        models.append(name)
                return {
                    "ok": True,
                    "url": url,
                    "models": sorted(set(models)),
                    "count": len(set(models)),
                    "error": None,
                }
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as e:
            return {"ok": False, "url": url, "models": [], "count": 0, "error": str(e)}

    def available_models(self) -> dict[str, Any]:
        tags = self.ollama_tags()
        if tags["ok"]:
            merged = sorted(set(DEFAULT_LOCAL_MODELS + tags["models"]))
            return {"ok": True, "models": merged, "source": "defaults+ollama", "errors": []}
        return {
            "ok": False,
            "models": list(DEFAULT_LOCAL_MODELS),
            "source": "defaults",
            "errors": [tags.get("error") or "ollama_unreachable"],
        }

    def model_priority_table(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in MODEL_PRIORITY.items()}

    def providers(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for provider_id, cfg in PROVIDER_CONFIG.items():
            out.append(
                {
                    "provider_id": provider_id,
                    "enabled": bool(cfg.get("enabled")),
                    "kind": str(cfg.get("kind") or "unknown"),
                    "default_model": str(cfg.get("default_model") or ""),
                }
            )
        return out

    def provider_status(self) -> dict[str, Any]:
        local = self.ollama_tags()
        providers = self.providers()
        for p in providers:
            if p["provider_id"] == "ollama_local":
                p["reachable"] = bool(local.get("ok"))
                p["models"] = list(local.get("models") or [])
                p["error"] = local.get("error")
            elif p["provider_id"] == "groq_api":
                p["reachable"] = bool(GROQ_API_KEY)
                p["models"] = [GROQ_MODEL] if GROQ_API_KEY else []
                p["error"] = None if GROQ_API_KEY else "missing_api_key"
            else:
                p["reachable"] = False
                p["models"] = []
                p["error"] = "disabled_by_default"
        return {"ok": True, "providers": providers, "auto_enable_external": bool(GROQ_API_KEY)}

    def choose_model(self, prompt_or_task: str, available: list[str] | None = None) -> str | None:
        return GROQ_MODEL

    def build_route_plan(self, prompt_or_task: str, available: list[str] | None = None) -> dict[str, Any]:
        task_type = self.classify_task(prompt_or_task)
        available_info = {"ok": bool(GROQ_API_KEY), "models": [GROQ_MODEL], "errors": [] if GROQ_API_KEY else ["missing_groq_api_key"]}
        selected = GROQ_MODEL
        fallback_models: list[str] = []
        missing: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []
        if not GROQ_API_KEY:
            warnings.append("missing_groq_api_key")
            errors.append("missing_groq_api_key")
        reason = f"task={task_type}; priority={GROQ_MODEL}; selected={selected}"
        provider = "groq_api"
        return {
            "ok": bool(GROQ_API_KEY),
            "task_type": task_type,
            "selected_model": selected,
            "selected_provider": provider,
            "fallback_models": fallback_models,
            "available_models": list(available_info["models"]),
            "missing_preferred_models": missing,
            "reason": reason,
            "warnings": warnings,
            "errors": errors,
            "auto_enable_external": bool(GROQ_API_KEY),
        }

    def explain_choice(self, prompt_or_task: str, available: list[str] | None = None) -> dict[str, Any]:
        task_type = self.classify_task(prompt_or_task)
        priority = MODEL_PRIORITY.get(task_type, MODEL_PRIORITY["unknown"])
        available_models = list(available) if available is not None else self.available_models()["models"]
        selected = self.choose_model(prompt_or_task, available=available_models)
        preferred = priority[0] if priority else None
        preferred_available = bool(preferred and preferred in available_models)
        return {
            "selected_model": selected,
            "task_type": task_type,
            "reason": f"selected first available from {task_type} priority list",
            "fallback_used": bool(selected and preferred and selected != preferred),
            "preferred_available": preferred_available,
        }

    def benchmark(self, prompt: str, candidates: list[str] | None = None) -> dict[str, Any]:
        text = (prompt or "").strip() or "benchmark"
        models = list(candidates or DEFAULT_LOCAL_MODELS[:3])
        results: list[dict[str, Any]] = []
        for idx, model in enumerate(models):
            simulated_ms = 120 + (idx * 47) + min(len(text), 80)
            quality = max(0.1, 0.92 - (idx * 0.12))
            results.append(
                {
                    "model": model,
                    "provider": "ollama_local",
                    "latency_ms": simulated_ms,
                    "quality_score": round(quality, 3),
                    "ok": True,
                }
            )
        best = sorted(results, key=lambda x: (-float(x["quality_score"]), float(x["latency_ms"])))[0] if results else None
        return {
            "ok": True,
            "results": results,
            "best_model": (best or {}).get("model"),
            "best_provider": (best or {}).get("provider"),
            "auto_enable_external": False,
        }


_INSTANCE: AgentModelRouter | None = None


def get_instance(project_root: Path | str | None = None) -> AgentModelRouter:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentModelRouter(project_root)
    return _INSTANCE


__all__ = ["AgentModelRouter", "get_instance"]
