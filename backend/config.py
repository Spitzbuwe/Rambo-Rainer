from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path(os.getenv("APPDATA", Path.home())) / "rainer-builder" / "config.json"

DEFAULTS = {
    "github_pat": "",
    "github_repo": "",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama-3.3-70b-versatile",
    "default_provider": "local",
    "max_parallel_tasks": 5,
    "log_level": "INFO",
}


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save(updates: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load()
    current.update(dict(updates or {}))
    CONFIG_PATH.write_text(json.dumps(current, ensure_ascii=True, indent=2), encoding="utf-8")


def get(key: str, fallback=None):
    cfg = load()
    env_map = {
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "openai_api_key": "OPENAI_API_KEY",
        "github_pat": "GITHUB_PAT",
        "github_repo": "GITHUB_REPO",
    }
    env_name = env_map.get(key)
    if env_name and os.getenv(env_name):
        return os.getenv(env_name)
    return cfg.get(key, fallback)
