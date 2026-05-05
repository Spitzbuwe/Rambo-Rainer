"""
Sichere Shell-Ausfuehrung fuer den autonomen Agent (Whitelist, kein shell=True).

Erweiterungen: breitere Whitelist (Dev-Tools), Rate-Limit, optionaler Sandbox-Modus,
Ergebnis-Cache fuer reine Versions-/Health-Abfragen, parallele Ausfuehrung nur fuer
triviale Health-Probes, strukturierte Fehlerobjekte, Audit-History.
"""
from __future__ import annotations

import copy
import logging
import os
import shlex
import subprocess
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Erste Token-Stems (oder Pfad-Stem) — kein shell=True, daher argv-basiert sicherer als freie Shell.
ALLOWED_EXE_STEMS = frozenset(
    {
        "python",
        "python3",
        "py",
        "pip",
        "pip3",
        "npm",
        "npx",
        "node",
        "git",
        "pytest",
        "cargo",
        "rustc",
        "make",
        "ninja",
        "cmake",
        "poetry",
        "uv",
        "ruff",
        "mypy",
        "eslint",
        "tsc",
        "prettier",
        "black",
        "isort",
        "pre-commit",
        "wasm-pack",
        "deno",
        "docker",
        "docker-compose",
        "terraform",
        "ansible-playbook",
        "gradlew",
        "gradle",
    }
)

FORBIDDEN_SUBSTRINGS = ("`", "&&", "||", "$(", "${", "\n", "\r")

SANDBOX_BLOCKED_STEMS = frozenset({"docker", "docker-compose", "terraform", "ansible-playbook"})

# Rate-Limit: pro Executor-Instanz (typisch eine pro App)
_DEFAULT_MAX_PER_MIN = 48
_CACHE_TTL_SEC = 45.0


def _executable_stem(token: str) -> str:
    return Path(str(token).strip('"').strip("'")).stem.lower()


def _normalize_argv_after_shlex(argv: list[str]) -> list[str]:
    if os.name != "nt" or len(argv) < 3 or argv[1] != "-c":
        return argv
    script = argv[2]
    if len(script) >= 2 and script[0] == script[-1] and script[0] in ("'", '"'):
        out = list(argv)
        out[2] = script[1:-1]
        return out
    return argv


def _is_allowed_argv(argv: list[str]) -> bool:
    if not argv:
        return False
    stem = _executable_stem(argv[0])
    if stem in ALLOWED_EXE_STEMS:
        return True
    low = argv[0].lower()
    return low in ("python", "python3", "py", "pip", "pip3", "npm", "npx", "node", "git", "pytest")


def _sandbox_blocks(stem: str) -> bool:
    if os.environ.get("RAINER_AGENT_SANDBOX", "").strip().lower() not in ("1", "true", "yes"):
        return False
    return stem.lower() in SANDBOX_BLOCKED_STEMS


def _is_cacheable_probe(parts: list[str]) -> bool:
    """Nur harmlose Lese-/Versionsaufrufe cachen."""
    if len(parts) < 2 or "-c" in parts:
        return False
    if any(";" in p for p in parts):
        return False
    rest = [p.lower() for p in parts[1:]]
    if rest == ["--version"] or rest == ["-v"] or rest == ["-version"]:
        return True
    if len(parts) == 2 and rest == ["version"]:
        return True
    if len(parts) >= 2 and rest[0] in ("--version", "-v", "--help", "-h"):
        return len(rest) == 1
    return False


def _is_parallel_safe_probe(parts: list[str]) -> bool:
    return _is_cacheable_probe(parts)


def _failure(
    *,
    error: str,
    code: str,
    cmd: str | None = None,
    hints: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "success": False,
        "error": error,
        "error_code": code,
        "hints": hints or [],
        "recovery": {
            "retry_suggested": code in ("TIMEOUT", "OS_ERROR", "RATE_LIMIT"),
            "check_command": code == "NOT_WHITELISTED",
            "simplify_command": code == "PARSE_ERROR",
        },
    }
    if cmd is not None:
        out["cmd"] = cmd
    if extra:
        out.update(extra)
    return out


class AgentExecutor:
    """
    Whitelist-Executor ohne shell=True, inkl. Rate-Limit, Cache, History, Audit-Level.
    """

    def __init__(
        self,
        project_root: Path | str,
        *,
        max_commands_per_minute: int = _DEFAULT_MAX_PER_MIN,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.execution_history: list[dict[str, Any]] = []
        self._rate_times: deque[float] = deque()
        self._rate_lock = threading.Lock()
        self.max_commands_per_minute = max(1, min(int(max_commands_per_minute), 200))
        self._result_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._cache_lock = threading.Lock()
        self._security = None
        self._env_manager = None
        try:
            from agent_security_hardened import get_instance as _get_security_instance

            self._security = _get_security_instance()
        except Exception:
            logger.debug("SecurityHardened nicht verfuegbar", exc_info=True)
        try:
            from agent_environments import get_instance as _get_env_instance

            self._env_manager = _get_env_instance()
        except Exception:
            logger.debug("EnvironmentManager nicht verfuegbar", exc_info=True)
        logger.info(
            "AgentExecutor initialisiert root=%s rate_limit=%s/min",
            self.project_root,
            self.max_commands_per_minute,
        )

    def _audit(self, **kwargs: Any) -> None:
        kwargs.setdefault("ts", time.time())
        self._record_history(kwargs)

    def _redact_text(self, text: str | None) -> str:
        raw = str(text or "")
        if self._security is None:
            return raw
        try:
            return str(self._security.redact_secrets(raw))
        except Exception:
            return raw

    def _security_audit_event(self, event_type: str, data: dict[str, Any], level: str = "info") -> None:
        if self._security is None:
            return
        try:
            self._security.audit_event(event_type=event_type, data=data, level=level)
        except Exception:
            logger.debug("security audit_event fehlgeschlagen", exc_info=True)

    def _resolve_cwd(self, cwd: str | None) -> Path:
        if not cwd:
            return self.project_root
        p = (self.project_root / str(cwd).replace("\\", "/").lstrip("/")).resolve()
        try:
            p.relative_to(self.project_root)
        except ValueError as e:
            raise ValueError(f"cwd ausserhalb Projektroot: {cwd}") from e
        return p

    def _record_history(self, entry: dict[str, Any]) -> None:
        self.execution_history.append(entry)
        if len(self.execution_history) > 300:
            self.execution_history = self.execution_history[-300:]

    def get_execution_history(self, limit: int = 10) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 100))
        return [copy.deepcopy(x) for x in self.execution_history[-lim:]]

    def clear_history(self) -> None:
        self.execution_history.clear()
        with self._cache_lock:
            self._result_cache.clear()
        logger.info("AgentExecutor history+cache geleert")

    def _rate_acquire(self) -> bool:
        now = time.time()
        window = 60.0
        with self._rate_lock:
            while self._rate_times and now - self._rate_times[0] > window:
                self._rate_times.popleft()
            if len(self._rate_times) >= self.max_commands_per_minute:
                return False
            self._rate_times.append(now)
        return True

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        with self._cache_lock:
            hit = self._result_cache.get(key)
            if not hit:
                return None
            exp, payload = hit
            if time.time() > exp:
                del self._result_cache[key]
                return None
            return copy.deepcopy(payload)

    def _cache_set(self, key: str, payload: dict[str, Any]) -> None:
        with self._cache_lock:
            self._result_cache[key] = (time.time() + _CACHE_TTL_SEC, copy.deepcopy(payload))
            if len(self._result_cache) > 128:
                for k in list(self._result_cache.keys())[:32]:
                    self._result_cache.pop(k, None)

    def execute_commands(
        self,
        commands: list[str],
        cwd: str | None = None,
        timeout: int = 120,
        *,
        parallel: bool = False,
    ) -> dict[str, Any]:
        if parallel:
            return self.execute_commands_parallel(commands, cwd=cwd, timeout=timeout)
        results: list[dict[str, Any]] = []
        for i, cmd in enumerate(commands):
            logger.info("execute_commands seq %s/%s", i + 1, len(commands))
            r = self.execute_command(cmd, cwd=cwd, timeout=timeout)
            results.append(r)
            if not r.get("success"):
                return {
                    "success": False,
                    "results": results,
                    "failed_at": i,
                    "total_executed": i + 1,
                    "mode": "sequential",
                }
        return {
            "success": True,
            "results": results,
            "failed_at": -1,
            "total_executed": len(commands),
            "mode": "sequential",
        }

    def execute_commands_parallel(
        self,
        commands: list[str],
        cwd: str | None = None,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Nur fuer kurze Health-/Versions-Probes; sonst Race auf dem Arbeitsbaum moeglich.
        Fallback: bei unsicherem Befehl sequentiell ausfuehren.
        """
        parsed: list[tuple[int, str, list[str]]] = []
        for i, cmd in enumerate(commands):
            try:
                parts = _normalize_argv_after_shlex(shlex.split(str(cmd).strip(), posix=os.name != "nt"))
            except ValueError:
                return {
                    "success": False,
                    "error": "Parallel-Modus: Parse-Fehler",
                    "failed_at": i,
                    "mode": "parallel_rejected",
                }
            if not parts or not _is_parallel_safe_probe(parts):
                logger.info("parallel unsicher, wechsle zu sequentiell ab Befehl %s", i)
                return self.execute_commands(commands, cwd=cwd, timeout=timeout, parallel=False)
            parsed.append((i, cmd, parts))

        results_map: dict[int, dict[str, Any]] = {}
        max_workers = min(6, len(commands))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futs = {
                pool.submit(self.execute_command, cmd, cwd, timeout): idx for idx, cmd, _ in parsed
            }
            for fut in as_completed(futs):
                idx = futs[fut]
                try:
                    results_map[idx] = fut.result()
                except Exception as e:
                    results_map[idx] = _failure(
                        error=str(e),
                        code="PARALLEL_WORKER",
                        hints=["Einzelbefehl pruefen", "sequentiell ausfuehren"],
                    )
        ordered = [results_map[i] for i in range(len(commands))]
        ok = all(r.get("success") for r in ordered)
        failed_at = next((i for i, r in enumerate(ordered) if not r.get("success")), -1)
        return {
            "success": ok,
            "results": ordered,
            "failed_at": failed_at if not ok else -1,
            "total_executed": len(commands),
            "mode": "parallel",
        }

    def execute_command(
        self,
        cmd: str,
        cwd: str | None = None,
        timeout: int = 120,
    ) -> dict[str, Any]:
        cmd = str(cmd or "").strip()
        if not cmd:
            out = _failure(error="Leerer Befehl", code="EMPTY_CMD")
            self._audit(cmd="", success=False, audit_level="denied", error=out["error"], error_code=out["error_code"])
            return out

        red_cmd = self._redact_text(cmd)
        security_payload: dict[str, Any] | None = None
        if self._security is not None:
            try:
                sanitize = self._security.sanitize_command(cmd)
                injection = self._security.detect_command_injection(cmd)
                traversal = self._security.detect_path_traversal(cmd)
                secrets = self._security.detect_secrets(cmd)
                risk = self._security.risk_score(cmd)
                security_payload = {
                    "sanitize": sanitize,
                    "injection": injection,
                    "path_traversal": traversal,
                    "secrets": secrets,
                    "risk": risk,
                }

                def _redact_obj(value: Any) -> Any:
                    if isinstance(value, str):
                        return self._redact_text(value)
                    if isinstance(value, list):
                        return [_redact_obj(x) for x in value]
                    if isinstance(value, dict):
                        return {k: _redact_obj(v) for k, v in value.items()}
                    return value

                security_payload = _redact_obj(security_payload)
                security_block = bool(
                    sanitize.get("blocked")
                    or injection.get("detected")
                    or traversal.get("detected")
                    or secrets.get("detected")
                    or risk.get("level") in ("high", "critical")
                )
                if security_block:
                    out = {
                        "success": False,
                        "audit_level": "blocked",
                        "error": "Security policy blocked command",
                        "error_code": "SECURITY_BLOCKED",
                        "security": security_payload,
                        "cmd": red_cmd,
                    }
                    self._audit(
                        cmd=red_cmd,
                        success=False,
                        audit_level="blocked",
                        error=out["error"],
                        error_code=out["error_code"],
                    )
                    self._security_audit_event(
                        "blocked/security",
                        {"cmd": red_cmd, "security": security_payload},
                        level="warning",
                    )
                    return out
            except Exception:
                logger.debug("security check fehlgeschlagen", exc_info=True)

        if self._env_manager is not None:
            try:
                env_raw = (os.environ.get("RAINER_ENV") or "").strip()
                if env_raw:
                    self._env_manager.set_environment(env_raw)
                env_now = self._env_manager.current_environment()
                env_eval = self._env_manager.validate_runtime_action("run_command", command=cmd)
                if not env_eval.get("allowed", True):
                    out = {
                        "success": False,
                        "audit_level": "blocked",
                        "error": "Environment policy blocked command",
                        "error_code": "ENV_POLICY_BLOCKED",
                        "environment": {"current": env_now, "validation": env_eval},
                        "cmd": red_cmd,
                    }
                    self._audit(
                        cmd=red_cmd,
                        success=False,
                        audit_level="blocked",
                        error=out["error"],
                        error_code=out["error_code"],
                    )
                    self._security_audit_event(
                        "blocked/environment",
                        {"cmd": red_cmd, "environment": out["environment"]},
                        level="warning",
                    )
                    return out
                self._security_audit_event(
                    "allowed/run",
                    {"cmd": red_cmd, "environment": env_now.get("name", ""), "action": "run_command"},
                    level="info",
                )
            except Exception:
                logger.debug("environment validation fehlgeschlagen", exc_info=True)

        if not self._rate_acquire():
            out = _failure(
                error=f"Rate-Limit: max. {self.max_commands_per_minute} Starts pro Minute.",
                code="RATE_LIMIT",
                cmd=red_cmd,
                hints=["Warte kurz", "Weniger parallele UI-Requests"],
            )
            self._audit(cmd=red_cmd, success=False, audit_level="denied", error=out["error"], error_code="RATE_LIMIT")
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "RATE_LIMIT"}, level="warning")
            return out

        cache_key = f"{cwd or ''}::{cmd}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.info("execute_command cache hit cmd=%s", cmd[:120])
            cached_out = copy.deepcopy(cached)
            if "stdout" in cached_out:
                cached_out["stdout"] = self._redact_text(cached_out.get("stdout"))
            if "stderr" in cached_out:
                cached_out["stderr"] = self._redact_text(cached_out.get("stderr"))
            self._audit(cmd=red_cmd, success=cached.get("success"), audit_level="cache_hit", cached=True)
            return {**cached_out, "cached": True}

        logger.info("execute_command start cwd=%s cmd=%s", cwd, cmd[:500])

        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in cmd:
                out = _failure(
                    error="Metazeichen im Befehl nicht erlaubt (Shell-Ketten/Substitution).",
                    code="FORBIDDEN_META",
                    cmd=red_cmd,
                    hints=["Befehl ohne && || $() ausfuehren", "Nur ein Programm + Argumente"],
                )
                logger.warning("execute_command Meta: %r", cmd[:200])
                self._audit(cmd=red_cmd, success=False, audit_level="blocked", error=out["error"], error_code=out["error_code"])
                self._security_audit_event("blocked/security", {"cmd": red_cmd, "reason": "FORBIDDEN_META"}, level="warning")
                return out
        try:
            parts = shlex.split(cmd, posix=os.name != "nt")
        except ValueError as e:
            out = _failure(
                error=f"Parse-Fehler: {e}",
                code="PARSE_ERROR",
                cmd=red_cmd,
                hints=["Anfuehrungszeichen pruefen", "Windows: shlex-inkompatible Zeichen vermeiden"],
            )
            logger.warning("execute_command Parse: %s", e)
            self._audit(cmd=red_cmd, success=False, audit_level="denied", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "PARSE_ERROR"}, level="warning")
            return out
        parts = _normalize_argv_after_shlex(parts)
        if not parts:
            out = _failure(error="Kein ausfuehrbares Programm nach Split.", code="NO_ARGV", cmd=red_cmd)
            self._audit(cmd=red_cmd, success=False, audit_level="denied", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "NO_ARGV"}, level="warning")
            return out
        stem = _executable_stem(parts[0])
        if _sandbox_blocks(stem):
            out = _failure(
                error=f"Sandbox: Programm '{stem}' ist in diesem Modus deaktiviert.",
                code="SANDBOX_BLOCK",
                cmd=red_cmd,
                hints=["RAINER_AGENT_SANDBOX deaktivieren", "Anderes Tool aus Whitelist nutzen"],
            )
            self._audit(cmd=red_cmd, success=False, audit_level="blocked", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("blocked/security", {"cmd": red_cmd, "reason": "SANDBOX_BLOCK"}, level="warning")
            return out
        if not _is_allowed_argv(parts):
            out = _failure(
                error=f"Programm nicht erlaubt: {parts[0]}",
                code="NOT_WHITELISTED",
                cmd=red_cmd,
                hints=["Nur Whitelist-Stems", "Pfad pruefen"],
                extra={"allowed_stems": sorted(ALLOWED_EXE_STEMS)},
            )
            logger.warning("execute_command nicht whitelisted: %s", parts[0])
            self._audit(cmd=red_cmd, success=False, audit_level="blocked", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("blocked/security", {"cmd": red_cmd, "reason": "NOT_WHITELISTED"}, level="warning")
            return out
        try:
            cwd_path = self._resolve_cwd(cwd)
        except ValueError as e:
            out = _failure(error=str(e), code="CWD_ESCAPE", cmd=red_cmd, hints=["cwd relativ zum Projekt setzen"])
            logger.warning("execute_command cwd: %s", e)
            self._audit(cmd=red_cmd, success=False, audit_level="denied", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("blocked/security", {"cmd": red_cmd, "reason": "CWD_ESCAPE"}, level="warning")
            return out
        if not cwd_path.is_dir():
            out = _failure(
                error=f"cwd existiert nicht: {cwd_path}",
                code="CWD_MISSING",
                cmd=red_cmd,
                hints=["Verzeichnis anlegen oder cwd weglassen"],
            )
            logger.warning("execute_command cwd fehlt: %s", cwd_path)
            self._audit(cmd=red_cmd, success=False, audit_level="denied", error=out["error"], error_code=out["error_code"])
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "CWD_MISSING"}, level="warning")
            return out

        start = time.time()
        run_env = os.environ.copy()
        run_env.setdefault("PYTHONUNBUFFERED", "1")
        try:
            run_kw: dict[str, Any] = {
                "cwd": str(cwd_path),
                "capture_output": True,
                "text": True,
                "timeout": max(5, min(int(timeout), 600)),
                "shell": False,
                "env": run_env,
            }
            if os.name == "nt":
                run_kw["encoding"] = "utf-8"
                run_kw["errors"] = "replace"
            logger.info("subprocess.run argv0=%s cwd=%s", parts[0], cwd_path)
            cp = subprocess.run(parts, **run_kw)
            elapsed = time.time() - start
            out = {
                "success": cp.returncode == 0,
                "stdout": self._redact_text((cp.stdout or "")[:8000]),
                "stderr": self._redact_text((cp.stderr or "")[:8000]),
                "returncode": cp.returncode,
                "elapsed": elapsed,
                "cmd": red_cmd,
                "error_code": None if cp.returncode == 0 else "NONZERO_EXIT",
                "hints": [] if cp.returncode == 0 else ["stderr lesen", "Befehl manuell im Projekt testen"],
            }
            if not out["success"]:
                out["error"] = f"Prozess beendete mit Code {cp.returncode}"
                out["recovery"] = {"retry_suggested": True, "check_command": True, "simplify_command": False}
            if out["success"]:
                logger.info("execute_command ok elapsed=%.3fs", elapsed)
            else:
                logger.warning("execute_command rc=%s stderr=%r", cp.returncode, (cp.stderr or "")[:400])
            self._audit(
                cmd=red_cmd,
                success=out["success"],
                audit_level="run",
                returncode=cp.returncode,
                elapsed=elapsed,
                stdout_len=len(out["stdout"] or ""),
                stderr_preview=self._redact_text((cp.stderr or "")[:500]),
            )
            self._security_audit_event(
                "success" if out["success"] else "failure",
                {"cmd": red_cmd, "returncode": cp.returncode, "elapsed": elapsed},
                level="info" if out["success"] else "warning",
            )
            if _is_cacheable_probe(parts) and out.get("success"):
                self._cache_set(cache_key, {k: v for k, v in out.items() if k != "cached"})
            return out
        except subprocess.TimeoutExpired:
            elapsed = time.time() - start
            out = _failure(
                error=f"Timeout nach {timeout}s",
                code="TIMEOUT",
                cmd=red_cmd,
                hints=["timeout erhoehen", "schwereren Schritt splitten"],
                extra={"elapsed": elapsed},
            )
            logger.error("execute_command Timeout cmd=%r", cmd[:200])
            self._audit(cmd=red_cmd, success=False, audit_level="run", error=out["error"], error_code="TIMEOUT", elapsed=elapsed)
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "TIMEOUT"}, level="warning")
            return out
        except OSError as e:
            logger.warning("execute_command OSError: %s", e)
            out = _failure(
                error=str(e),
                code="OS_ERROR",
                cmd=red_cmd,
                hints=["Binary installiert?", "PATH pruefen"],
                extra={"exception": type(e).__name__},
            )
            out["error"] = self._redact_text(str(out.get("error", "")))
            self._audit(cmd=red_cmd, success=False, audit_level="run", error=out["error"], error_code="OS_ERROR")
            self._security_audit_event("failure", {"cmd": red_cmd, "error_code": "OS_ERROR"}, level="warning")
            return out
