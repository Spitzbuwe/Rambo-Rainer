"""Runtime environment profiles for local/staging/production security settings."""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AgentEnv(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


_SAFE_COMMANDS = [
    "python -m py_compile",
    "python -m pytest",
    "node --check",
    "npm run build",
    "git status",
    "git diff",
]

_DENIED_COMMANDS = [
    "rm -rf",
    "del /s /q",
    "format",
    "reg add",
    "reg delete",
]

_BASE_PROFILES: dict[str, dict[str, Any]] = {
    "development": {
        "name": "development",
        "security_level": "medium",
        "debug_enabled": True,
        "auto_apply_allowed": True,
        "network_allowed": "limited",
        "shell_mode": "allowlisted",
        "features": {
            "local_agent": True,
            "direct_mode": True,
            "auto_repair": True,
            "external_llm": False,
            "destructive_commands": False,
        },
        "allowed_commands": list(_SAFE_COMMANDS),
        "denied_commands": list(_DENIED_COMMANDS),
    },
    "staging": {
        "name": "staging",
        "security_level": "high",
        "debug_enabled": True,
        "auto_apply_allowed": False,
        "network_allowed": "limited",
        "shell_mode": "strict_allowlist",
        "features": {
            "local_agent": True,
            "direct_mode": True,
            "auto_repair": False,
            "external_llm": False,
            "destructive_commands": False,
        },
        "allowed_commands": list(_SAFE_COMMANDS),
        "denied_commands": list(_DENIED_COMMANDS),
    },
    "production": {
        "name": "production",
        "security_level": "critical",
        "debug_enabled": False,
        "auto_apply_allowed": False,
        "network_allowed": "none",
        "shell_mode": "strict_allowlist",
        "features": {
            "local_agent": True,
            "direct_mode": True,
            "auto_repair": False,
            "external_llm": False,
            "destructive_commands": False,
        },
        "allowed_commands": list(_SAFE_COMMANDS),
        "denied_commands": list(_DENIED_COMMANDS),
    },
}


@dataclass(frozen=True)
class AgentEnvironmentConfig:
    name: AgentEnv
    security_level: str
    log_level: str
    feature_async_agent: bool
    feature_mega_status: bool
    feature_block_secrets_in_cmd: bool
    max_agent_iterations: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name.value,
            "security_level": self.security_level,
            "log_level": self.log_level,
            "features": {
                "async_agent": self.feature_async_agent,
                "mega_status": self.feature_mega_status,
                "block_secrets_in_cmd": self.feature_block_secrets_in_cmd,
            },
            "max_agent_iterations": self.max_agent_iterations,
        }


class EnvironmentManager:
    def __init__(self) -> None:
        self._profiles = copy.deepcopy(_BASE_PROFILES)
        self._current = self._normalize_env_name(os.getenv("RAINER_ENV") or "development")

    @staticmethod
    def _normalize_env_name(name: str | None) -> str:
        raw = (name or "").strip().lower()
        if raw in ("dev", "development"):
            return "development"
        if raw in ("stage", "staging"):
            return "staging"
        if raw in ("prod", "production"):
            return "production"
        return "development"

    def current_environment(self) -> dict[str, Any]:
        return {
            "name": self._current,
            "profile": self.get_profile(self._current),
        }

    def set_environment(self, name: str) -> dict[str, Any]:
        raw = (name or "").strip().lower()
        valid_aliases = {
            "development": "development",
            "dev": "development",
            "staging": "staging",
            "stage": "staging",
            "production": "production",
            "prod": "production",
        }
        if raw not in valid_aliases:
            return {"ok": False, "reason": "invalid_environment", "requested": name}
        normalized = valid_aliases[raw]
        self._current = normalized
        os.environ["RAINER_ENV"] = normalized
        return {"ok": True, "environment": normalized}

    def get_profile(self, name: str | None = None) -> dict[str, Any]:
        env = self._normalize_env_name(name or self._current)
        profile = self._profiles.get(env)
        if profile is None:
            raise ValueError(f"Unknown environment profile: {name}")
        return copy.deepcopy(profile)

    def list_profiles(self) -> list[str]:
        return sorted(self._profiles.keys())

    def is_feature_enabled(self, feature: str, env: str | None = None) -> bool:
        profile = self.get_profile(env)
        return bool(profile.get("features", {}).get(feature, False))

    def security_level(self, env: str | None = None) -> str:
        return str(self.get_profile(env).get("security_level", "medium"))

    def allowed_commands(self, env: str | None = None) -> list[str]:
        return list(self.get_profile(env).get("allowed_commands", []))

    def denied_commands(self, env: str | None = None) -> list[str]:
        return list(self.get_profile(env).get("denied_commands", []))

    def validate_runtime_action(self, action: str, command: str | None = None, env: str | None = None) -> dict[str, Any]:
        profile = self.get_profile(env)
        cmd = (command or "").strip()
        cmd_low = cmd.lower()
        action_low = (action or "").strip().lower()
        reasons: list[str] = []
        allowed = True

        for denied in profile.get("denied_commands", []):
            if denied in cmd_low:
                allowed = False
                reasons.append(f"denied_command:{denied}")

        if action_low in ("delete", "destructive", "format_disk", "wipe"):
            allowed = False
            reasons.append("destructive_action_blocked")

        if profile.get("network_allowed") == "none" and action_low in (
            "network_request",
            "external_http",
            "download",
            "upload",
        ):
            allowed = False
            reasons.append("network_blocked_in_production")
        if profile.get("network_allowed") == "none" and cmd:
            if any(k in cmd_low for k in ("http://", "https://", "curl ", "wget ")):
                allowed = False
                reasons.append("network_command_blocked_in_production")

        if cmd and profile.get("shell_mode") == "strict_allowlist":
            prefixes = tuple(profile.get("allowed_commands", []))
            if not any(cmd.startswith(p) for p in prefixes):
                allowed = False
                reasons.append("command_not_on_allowlist")

        return {
            "allowed": allowed,
            "environment": profile["name"],
            "action": action,
            "command": command,
            "reasons": reasons,
        }

    def export_config(self) -> dict[str, Any]:
        return {"current_environment": self._current, "profiles": copy.deepcopy(self._profiles)}

    def import_config(self, data: dict) -> dict:
        if not isinstance(data, dict):
            return {"ok": False, "reason": "invalid_payload"}
        profiles = data.get("profiles")
        if not isinstance(profiles, dict):
            return {"ok": False, "reason": "missing_profiles"}
        valid = {"development", "staging", "production"}
        if not valid.issubset(set(profiles.keys())):
            return {"ok": False, "reason": "profiles_incomplete"}
        self._profiles = copy.deepcopy({k: profiles[k] for k in valid})
        env = self._normalize_env_name(str(data.get("current_environment", "development")))
        self._current = env
        return {"ok": True, "current_environment": self._current}

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "ready",
            "current_environment": self._current,
            "profile_count": len(self._profiles),
        }


_INSTANCE: EnvironmentManager | None = None


def get_instance() -> EnvironmentManager:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = EnvironmentManager()
    return _INSTANCE


def detect_agent_environment() -> AgentEnv:
    env = EnvironmentManager._normalize_env_name(os.getenv("RAINER_ENV") or os.getenv("RAINER_AGENT_ENV") or os.getenv("FLASK_ENV"))
    return AgentEnv(env)


def get_agent_environment_config() -> AgentEnvironmentConfig:
    manager = get_instance()
    profile = manager.get_profile()
    env = AgentEnv(profile["name"])
    iter_default = {"development": 8, "staging": 6, "production": 5}[profile["name"]]
    return AgentEnvironmentConfig(
        name=env,
        security_level=profile["security_level"],
        log_level=os.environ.get("RAINER_LOG_LEVEL", "DEBUG" if env is AgentEnv.DEVELOPMENT else "INFO"),
        feature_async_agent=True,
        feature_mega_status=True,
        feature_block_secrets_in_cmd=(profile["security_level"] in ("high", "critical")),
        max_agent_iterations=int(os.environ.get("RAINER_AGENT_MAX_ITER", str(iter_default))),
    )


def apply_agent_environment_to_os(cfg: AgentEnvironmentConfig | None = None) -> AgentEnvironmentConfig:
    cfg = cfg or get_agent_environment_config()
    os.environ.setdefault("RAINER_ENV", cfg.name.value)
    if cfg.name is AgentEnv.PRODUCTION:
        os.environ.setdefault("RAINER_AGENT_SANDBOX", "1")
    return cfg


__all__ = [
    "AgentEnv",
    "AgentEnvironmentConfig",
    "EnvironmentManager",
    "get_instance",
    "detect_agent_environment",
    "get_agent_environment_config",
    "apply_agent_environment_to_os",
]
