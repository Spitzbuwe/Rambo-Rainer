"""
Hybrid Intelligence Engine für Rainer Build
Optionales KI-Gehirn für Analyse, Planung und bessere Antworten.
"""
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Optionale Abhängigkeiten - kein harter Absturz bei Fehlen
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from dotenv import load_dotenv
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

# API-Clients - optional
try:
    import groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# .env optional laden
if DOTENV_AVAILABLE:
    try:
        load_dotenv()
    except Exception:
        pass


class HybridEngine:
    """Zentrale Hybrid Engine für Multi-Provider KI-Zugriff."""

    def __init__(self):
        self.workstream: List[Dict[str, Any]] = []
        self.providers = {
            "vllm": self._check_vllm(),
            "ollama": self._check_ollama(),
            "groq": GROQ_AVAILABLE and bool(os.getenv("GROQ_API_KEY")),
            "gemini": GEMINI_AVAILABLE and bool(os.getenv("GOOGLE_API_KEY")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
        }

    def _check_vllm(self) -> bool:
        """Prüft ob lokaler vLLM läuft."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            r = requests.get("http://localhost:8000/health", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def _check_ollama(self) -> bool:
        """Prüft ob Ollama läuft."""
        if not REQUESTS_AVAILABLE:
            return False
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    def add_workstream_event(self, phase: str, level: str, title: str, detail: str = "", status: str = "done"):
        """Fügt ein Workstream-Event hinzu (normalisiertes Format)."""
        event = {
            "ts": datetime.now().isoformat(),
            "phase": phase,
            "level": level,
            "title": title,
            "detail": detail,
            "status": status,
        }
        self.workstream.append(event)
        return event

    def get_available_providers(self) -> Dict[str, bool]:
        """Gibt verfügbare Provider zurück."""
        return {k: v for k, v in self.providers.items() if v}

    def is_available(self) -> bool:
        """Prüft ob mindestens ein Provider verfügbar ist."""
        return any(self.providers.values())

    # === Provider-API-Calls ===

    def _call_vllm(self, prompt: str) -> Optional[str]:
        """Ruft lokalen vLLM auf."""
        if not REQUESTS_AVAILABLE:
            return None
        try:
            self.add_workstream_event("inference", "info", "vLLM Anfrage", "Lokales vLLM...", "running")
            r = requests.post(
                "http://localhost:8000/v1/chat/completions",
                json={
                    "model": "local",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.add_workstream_event("inference", "success", "vLLM Antwort", f"{len(result)} Zeichen", "done")
                return result
        except Exception as e:
            self.add_workstream_event("inference", "error", "vLLM Fehler", str(e)[:100], "failed")
        return None

    def _call_ollama(self, model: str, prompt: str) -> Optional[str]:
        """Ruft Ollama auf."""
        if not REQUESTS_AVAILABLE:
            return None
        try:
            self.add_workstream_event("inference", "info", "Ollama Anfrage", f"Modell: {model}", "running")
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model or "llama3.2",
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.7, "num_predict": 2000},
                },
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                result = data.get("response", "")
                self.add_workstream_event("inference", "success", "Ollama Antwort", f"{len(result)} Zeichen", "done")
                return result
        except Exception as e:
            self.add_workstream_event("inference", "error", "Ollama Fehler", str(e)[:100], "failed")
        return None

    def _call_groq(self, prompt: str) -> Optional[str]:
        """Ruft Groq API auf."""
        if not GROQ_AVAILABLE:
            return None
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        try:
            self.add_workstream_event("inference", "info", "Groq Anfrage", "Groq Cloud...", "running")
            client = groq.Client(api_key=api_key)
            response = client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000,
            )
            result = response.choices[0].message.content
            self.add_workstream_event("inference", "success", "Groq Antwort", f"{len(result)} Zeichen", "done")
            return result
        except Exception as e:
            self.add_workstream_event("inference", "error", "Groq Fehler", str(e)[:100], "failed")
        return None

    def _call_gemini(self, prompt: str, use_pro: bool = False) -> Optional[str]:
        """Ruft Google Gemini API auf."""
        if not GEMINI_AVAILABLE:
            return None
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            self.add_workstream_event("inference", "info", "Gemini Anfrage", "Google AI...", "running")
            genai.configure(api_key=api_key)
            model_name = "gemini-2.5-pro-preview-05-06" if use_pro else "gemini-2.5-flash-preview-05-06"
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            result = response.text if hasattr(response, "text") else str(response)
            self.add_workstream_event("inference", "success", "Gemini Antwort", f"{len(result)} Zeichen", "done")
            return result
        except Exception as e:
            self.add_workstream_event("inference", "error", "Gemini Fehler", str(e)[:100], "failed")
        return None

    def _call_openrouter(self, prompt: str) -> Optional[str]:
        """Ruft OpenRouter API auf."""
        if not REQUESTS_AVAILABLE:
            return None
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return None
        try:
            self.add_workstream_event("inference", "info", "OpenRouter Anfrage", "Multi-Provider...", "running")
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "anthropic/claude-3.5-sonnet",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                self.add_workstream_event("inference", "success", "OpenRouter Antwort", f"{len(result)} Zeichen", "done")
                return result
        except Exception as e:
            self.add_workstream_event("inference", "error", "OpenRouter Fehler", str(e)[:100], "failed")
        return None

    # === Hauptfunktionen ===

    def ask(self, prompt: str, preferred_provider: Optional[str] = None) -> Dict[str, Any]:
        """
        Reine KI-Anfrage ohne Ausführung.
        Für Analyse, Planung, Erklärungen.
        """
        self.workstream = []
        self.add_workstream_event("start", "info", "Hybrid Anfrage", prompt[:80], "done")

        if not self.is_available():
            self.add_workstream_event("error", "error", "Kein Provider", "Keine Hybrid-LLM verfügbar", "failed")
            return {
                "ok": False,
                "error": "Keine Hybrid-LLM verfügbar. Bitte API-Key konfigurieren oder lokalen Service starten.",
                "workstream_events": self.workstream,
                "available_providers": self.get_available_providers(),
            }

        # Provider-Strategie
        providers_to_try = []
        if preferred_provider and self.providers.get(preferred_provider):
            providers_to_try.append(preferred_provider)
        # Fallback-Reihenfolge: Lokal -> Cloud
        for p in ["vllm", "ollama", "groq", "gemini", "openrouter"]:
            if self.providers.get(p) and p not in providers_to_try:
                providers_to_try.append(p)

        self.add_workstream_event("routing", "info", "Provider-Auswahl", f"Versuche: {', '.join(providers_to_try)}", "done")

        # Versuche Provider
        for provider in providers_to_try:
            result = None
            if provider == "vllm":
                result = self._call_vllm(prompt)
            elif provider == "ollama":
                result = self._call_ollama("llama3.2", prompt)
            elif provider == "groq":
                result = self._call_groq(prompt)
            elif provider == "gemini":
                result = self._call_gemini(prompt, use_pro=False)
            elif provider == "openrouter":
                result = self._call_openrouter(prompt)

            if result:
                self.add_workstream_event("final", "success", "Antwort fertig", f"Provider: {provider}", "done")
                return {
                    "ok": True,
                    "response": result,
                    "provider": provider,
                    "workstream_events": self.workstream,
                    "prompt_length": len(prompt),
                    "response_length": len(result),
                }

        self.add_workstream_event("final", "error", "Alle Provider fehlgeschlagen", "", "failed")
        return {
            "ok": False,
            "error": "Alle verfügbaren Provider konnten keine Antwort liefern.",
            "workstream_events": self.workstream,
            "available_providers": self.get_available_providers(),
        }


# Globale Instanz
hybrid_engine = HybridEngine()


def execute_intelligent_hybrid(prompt: str, response_style: Optional[str] = None) -> Dict[str, Any]:
    """
    Wrapper für Hybrid-Anfragen.
    Nicht für Datei-Operationen!
    """
    engine = HybridEngine()

    # Prüfe ob es eine reine Analyse-Anfrage ist
    task_lower = prompt.lower()
    blocked_patterns = [
        "erstelle datei", "erstelle nur die datei", "ändere datei", "aendere datei",
        "lösche datei", "loesche datei", "delete file", "create file",
        "baue electron", "build electron", "npm install", "build_desktop.py",
        "installer", ".exe", "write file", "modify file"
    ]

    for pattern in blocked_patterns:
        if pattern in task_lower:
            return {
                "ok": False,
                "error": f"Hybrid Engine nicht für Datei-/Build-Operationen zuständig. Verwende /api/direct-run oder /api/intelligent-run. Erkannt: '{pattern}'",
                "blocked": True,
                "workstream_events": engine.workstream,
            }

    # Reine Analyse-Anfrage
    return engine.ask(prompt)
