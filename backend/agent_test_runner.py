from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path


class TestRunnerAgent:
    __test__ = False
    def __init__(self, app_root: Path):
        self.app_root = Path(app_root).resolve()
        self.max_output_bytes = 80 * 1024
        self.timeout_seconds = 60
        self.allowed_checks: dict[str, list[str]] = {
            "pytest_all": ["python", "-m", "pytest", "tests", "-q"],
            "py_compile_main": ["python", "-m", "py_compile", "backend/main.py"],
            "node_check_app": ["node", "--check", "frontend/app.js"],
            "level20_diff_tests": ["python", "-m", "pytest", "tests/test_agent_level20_diff_viewer_api.py", "-q"],
            "level20_file_tests": ["python", "-m", "pytest", "tests/test_agent_level20_file_viewer_api.py", "-q"],
            "level20_explorer_tests": ["python", "-m", "pytest", "tests/test_agent_level20_explorer_api.py", "-q"],
        }

    def _truncate_output(self, stdout: str, stderr: str, max_bytes: int) -> tuple[str, str, bool]:
        out = str(stdout or "")
        err = str(stderr or "")
        limit = max(1, int(max_bytes))
        out_b = out.encode("utf-8", errors="replace")
        err_b = err.encode("utf-8", errors="replace")
        total = len(out_b) + len(err_b)
        if total <= limit:
            return out, err, False
        if len(out_b) >= limit:
            return out_b[:limit].decode("utf-8", errors="replace"), "", True
        remain = limit - len(out_b)
        return out, err_b[:remain].decode("utf-8", errors="replace"), True

    def list_checks(self) -> list[str]:
        return sorted(self.allowed_checks.keys())

    def recommend_checks(self, *, task: str = "", files: list[str] | None = None) -> dict[str, object]:
        t = str(task or "").lower()
        norm_files = [str(f or "").replace("\\", "/").strip().lower() for f in list(files or []) if str(f or "").strip()]
        checks: list[str] = []
        if "backend/" in " ".join(norm_files) or "api" in t or "backend" in t:
            checks.append("py_compile_main")
        if "frontend/" in " ".join(norm_files) or "ui" in t or "frontend" in t:
            checks.append("node_check_app")
        if "test" in t or any(p.startswith("tests/") for p in norm_files) or not checks:
            checks.append("pytest_all")
        # Keep order and uniqueness
        seen = set()
        ordered = []
        for c in checks:
            if c not in seen and c in self.allowed_checks:
                seen.add(c)
                ordered.append(c)
        return {"ok": True, "recommended_checks": ordered, "count": len(ordered)}

    def _parse_failed_tests(self, text: str) -> list[str]:
        out = []
        for m in re.findall(r"(tests[\\/][A-Za-z0-9_./\\-]+::[A-Za-z0-9_./\\-]+)", str(text or "")):
            t = m.replace("\\", "/")
            if t not in out:
                out.append(t)
        return out

    def _parse_failed_files(self, text: str) -> list[str]:
        out = []
        for m in re.findall(r"([A-Za-z0-9_./\\-]+\.(?:py|js|ts|jsx|tsx|html|css|json|md))", str(text or "")):
            p = m.replace("\\", "/")
            if p.startswith("/") or ".." in p.split("/"):
                continue
            if p not in out:
                out.append(p)
        return out

    def _is_flaky_check(self, check_name: str) -> bool:
        key = str(check_name or "").strip().lower()
        return key in {"pytest_all", "level20_diff_tests", "level20_file_tests", "level20_explorer_tests"}

    def run_allowed_check(self, check_name: str) -> dict[str, object]:
        warnings: list[str] = []
        errors: list[str] = []
        key = str(check_name or "").strip()
        cmd = self.allowed_checks.get(key)
        if not cmd:
            return {
                "ok": False,
                "check": key,
                "command": [],
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "duration_ms": 0,
                "truncated": False,
                "warnings": warnings,
                "errors": ["unknown_check"],
            }

        started = time.time()
        attempts = 1
        try:
            cp = subprocess.run(
                cmd,
                cwd=str(self.app_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as ex:
            duration_ms = int((time.time() - started) * 1000)
            out_t, err_t, truncated = self._truncate_output(
                ex.stdout or "",
                ex.stderr or "",
                self.max_output_bytes,
            )
            errors.append("timeout")
            warnings.append(f"check_timeout_{self.timeout_seconds}s")
            return {
                "ok": False,
                "check": key,
                "command": cmd,
                "returncode": -1,
                "stdout": out_t,
                "stderr": err_t,
                "duration_ms": duration_ms,
                "truncated": truncated,
                "warnings": warnings,
                "errors": errors,
            }
        except Exception as ex:  # noqa: BLE001
            duration_ms = int((time.time() - started) * 1000)
            errors.append(str(ex))
            return {
                "ok": False,
                "check": key,
                "command": cmd,
                "returncode": -1,
                "stdout": "",
                "stderr": "",
                "duration_ms": duration_ms,
                "truncated": False,
                "warnings": warnings,
                "errors": errors,
            }

        duration_ms = int((time.time() - started) * 1000)
        out_t, err_t, truncated = self._truncate_output(cp.stdout or "", cp.stderr or "", self.max_output_bytes)
        # Retry only for known flaky checks and only on failure.
        if int(cp.returncode) != 0 and self._is_flaky_check(key):
            attempts = 2
            try:
                cp_retry = subprocess.run(
                    cmd,
                    cwd=str(self.app_root),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                    timeout=self.timeout_seconds,
                )
                duration_ms = int((time.time() - started) * 1000)
                cp = cp_retry
                out_t, err_t, truncated = self._truncate_output(cp.stdout or "", cp.stderr or "", self.max_output_bytes)
                warnings.append("flaky_retry_used")
            except Exception:
                warnings.append("flaky_retry_failed")
        if truncated:
            warnings.append("output_truncated")
        ok = int(cp.returncode) == 0
        if not ok:
            errors.append("check_failed")
        combined = (str(out_t or "") + "\n" + str(err_t or "")).strip()
        failed_files = self._parse_failed_files(combined) if not ok else []
        failed_tests = self._parse_failed_tests(combined) if not ok else []
        error_summary = ""
        if not ok:
            if "timeout" in combined.lower():
                error_summary = "timeout"
            elif "syntaxerror" in combined.lower():
                error_summary = "syntax_error"
            elif "assertionerror" in combined.lower() or "failed" in combined.lower():
                error_summary = "test_failure"
            else:
                error_summary = "check_failed"
        return {
            "ok": ok,
            "check": key,
            "command": cmd,
            "returncode": int(cp.returncode),
            "stdout": out_t,
            "stderr": err_t,
            "duration_ms": duration_ms,
            "truncated": truncated,
            "attempts": attempts,
            "retry_performed": attempts > 1,
            "failed_files": failed_files,
            "failed_tests": failed_tests,
            "error_summary": error_summary,
            "warnings": warnings,
            "errors": errors,
        }

    def health(self) -> dict[str, object]:
        return {
            "ok": True,
            "agent": "test_runner",
            "app_root": str(self.app_root),
            "allowed_checks": self.list_checks(),
            "timeout_seconds": self.timeout_seconds,
            "max_output_bytes": self.max_output_bytes,
        }


_INSTANCE: TestRunnerAgent | None = None


def get_instance(app_root: Path | None = None) -> TestRunnerAgent:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = TestRunnerAgent(app_root or Path("."))
    return _INSTANCE
