"""
Hybrid-Ollama-Router: Quick vs. Detailed Modell je nach Prompt.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

_DEFAULT_QUICK_NAME = "mistral:latest"
_DEFAULT_DETAILED_NAME = "deepseek-coder:33b"


class HybridOptimizer:
    """Waehlt schnelles oder starkes Modell anhand einfacher Prompt-Heuristik."""

    def __init__(self, ollama_url: str | None = None) -> None:
        self.ollama_url = (ollama_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.quick_model = os.getenv("HYBRID_QUICK_MODEL", _DEFAULT_QUICK_NAME)
        self.detailed_model = os.getenv("HYBRID_DETAILED_MODEL", _DEFAULT_DETAILED_NAME)
        self.session = requests.Session()
        self.check_models()

    def check_models(self) -> bool:
        try:
            response = self.session.get(f"{self.ollama_url}/api/tags", timeout=2)
            if response.status_code == 200:
                models = response.json().get("models") or []
                names = [m.get("name") for m in models if isinstance(m, dict) and m.get("name")]
                logger.info("Ollama erreichbar, Modelle (Auszug): %s", names[:5])
                return True
        except (requests.RequestException, OSError, ValueError, TypeError) as e:
            logger.warning("Ollama nicht erreichbar: %s", e)
        return False

    def is_detailed_query(self, prompt: str) -> bool:
        detailed_keywords = (
            "analysiere",
            "analysier",
            "analyse",
            "designe",
            "design",
            "architektur",
            "architecture",
            "optimiere",
            "optimierung",
            "performance",
            "refactor",
            "refactoring",
            "sicherheit",
            "security",
            "vulnerabilit",
            "skalierung",
            "scaling",
            "scalability",
            "pattern",
            "patterns",
            "best practice",
            "best-practice",
            "warum",
            "why",
            "reason",
            "begruend",
            "detailliert",
            "ausfuehrlich",
            "comprehensive",
            "alternative",
            "comparison",
            "vergleich",
            "trade-off",
            "tradeoff",
            "edge case",
            "error handling",
            "fehlerbehandlung",
        )
        pl = (prompt or "").lower()
        score = sum(1 for kw in detailed_keywords if kw in pl)
        return score >= 1 or len(prompt or "") > 300

    def _get_system_prompt(self, mode: str) -> str:
        from system_prompts import SYSTEM_PROMPT_DETAILED, SYSTEM_PROMPT_QUICK

        return SYSTEM_PROMPT_DETAILED if mode == "detailed" else SYSTEM_PROMPT_QUICK

    def _get_chain_of_thought_prefix(self, mode: str) -> str:
        from system_prompts import CHAIN_OF_THOUGHT_DETAILED

        return CHAIN_OF_THOUGHT_DETAILED if mode == "detailed" else "Kurz denken: Problem -> Loesung -> Code."

    def _get_output_format(self, mode: str) -> str:
        from system_prompts import OUTPUT_FORMAT_DETAILED, OUTPUT_FORMAT_QUICK

        return OUTPUT_FORMAT_DETAILED if mode == "detailed" else OUTPUT_FORMAT_QUICK

    def _get_few_shot_examples(self, mode: str) -> str:
        from system_prompts import FEW_SHOT_GOOD_CODE

        return FEW_SHOT_GOOD_CODE if mode == "detailed" else ""

    def _build_user_prompt(self, prompt: str, context: str, mode: str) -> str:
        cot = self._get_chain_of_thought_prefix(mode)
        fmt = self._get_output_format(mode)
        ex = self._get_few_shot_examples(mode)
        parts = [cot, "", fmt]
        if ex:
            parts.extend(["", ex])
        parts.extend(
            [
                "",
                "KONTEXT (falls vorhanden):",
                context if context else "[Kein zusaetzlicher Kontext]",
                "",
                "BENUTZER-AUFTRAG:",
                prompt,
            ]
        )
        return "\n".join(parts)

    def execute_optimized(
        self,
        prompt: str,
        context: str = "",
        system_prompt: str | None = None,
        timeout_quick: int | None = None,
        timeout_detailed: int | None = None,
    ) -> dict[str, Any]:
        mode = "detailed" if self.is_detailed_query(prompt) else "quick"
        model = self.detailed_model if mode == "detailed" else self.quick_model
        sys_p = (system_prompt or "").strip() or self._get_system_prompt(mode)
        user_prompt = self._build_user_prompt(prompt, context, mode)
        tq = int(timeout_quick or os.getenv("HYBRID_TIMEOUT_QUICK_SEC", "120"))
        td = int(timeout_detailed or os.getenv("HYBRID_TIMEOUT_DETAILED_SEC", "300"))
        timeout = td if mode == "detailed" else tq

        logger.info("Hybrid mode=%s model=%s", mode, model)
        start = time.time()
        elapsed = 0.0
        try:
            response = self.session.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": model,
                    "system": sys_p,
                    "prompt": user_prompt,
                    "stream": False,
                    "temperature": 0.55 if mode == "detailed" else 0.5,
                    "top_k": 40 if mode == "detailed" else 35,
                    "top_p": 0.9,
                    "num_ctx": 6144,
                },
                timeout=timeout,
            )
            elapsed = time.time() - start
            response.raise_for_status()
            payload = response.json() or {}
            text = str(payload.get("response") or "").strip()
            return {
                "success": True,
                "response": text,
                "model": model,
                "mode": mode,
                "elapsed_seconds": elapsed,
                "tokens_generated": int(payload.get("eval_count") or 0),
                "quality_estimate": 4.8 if mode == "detailed" else 4.0,
            }
        except requests.Timeout:
            elapsed = time.time() - start
            logger.error("Timeout model=%s after %.1fs", model, elapsed)
            return {
                "success": False,
                "error": f"Timeout nach {elapsed:.1f}s",
                "model": model,
                "mode": mode,
            }
        except (requests.RequestException, OSError, ValueError, TypeError) as e:
            elapsed = time.time() - start
            logger.error("Hybrid generate failed: %s", e)
            return {
                "success": False,
                "error": str(e),
                "model": model,
                "mode": mode,
            }


hybrid_optimizer = HybridOptimizer()
