"""Git/project integration utilities with safe readonly commands."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

_UNSAFE_PREFIXES = ("Downloads/", "node_modules/", ".rainer_agent/", "dist/", "build/")
_MSG_RE = re.compile(r"^(feat\([^)]+\):|fix\([^)]+\):|test\([^)]+\):|docs:|chore:|refactor:|build:|perf:)\s+.+")


class AgentGitIntegration:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def _run_git(self, root: str | Path, args: list[str]) -> dict[str, Any]:
        cwd = Path(root).resolve()
        try:
            cp = subprocess.run(
                ["git", *args],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=20,
            )
            return {
                "ok": cp.returncode == 0,
                "returncode": cp.returncode,
                "stdout": (cp.stdout or "").strip(),
                "stderr": (cp.stderr or "").strip(),
                "cmd": ["git", *args],
            }
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(e), "cmd": ["git", *args]}

    def is_git_repo(self, root: str | Path) -> dict:
        root_path = Path(root).resolve()
        git_marker = root_path / ".git"
        if not git_marker.exists():
            return {"ok": False, "is_repo": False, "error": "missing_git_marker"}
        r = self._run_git(root, ["rev-parse", "--is-inside-work-tree"])
        inside = r["ok"] and r["stdout"].lower() == "true"
        return {"ok": inside, "is_repo": inside, "error": None if inside else r["stderr"]}

    def _parse_status_short(self, text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in (text or "").splitlines():
            if not line.strip():
                continue
            status = line[:2]
            if len(line) > 2 and line[2] == " ":
                path = line[3:]
            else:
                path = line[2:]
            rows.append({"status": status, "path": path.replace("\\", "/")})
        return rows

    def git_status(self, root: str | Path) -> dict:
        repo = self.is_git_repo(root)
        if not repo["is_repo"]:
            return {"ok": False, "error": "not_a_git_repo", "entries": []}
        r = self._run_git(root, ["status", "--short"])
        if not r["ok"]:
            return {"ok": False, "error": r["stderr"], "entries": []}
        entries = self._parse_status_short(r["stdout"])
        return {"ok": True, "entries": entries, "raw": r["stdout"]}

    def changed_files(self, root: str | Path) -> dict:
        st = self.git_status(root)
        if not st["ok"]:
            return {"ok": False, "error": st["error"]}
        modified: list[str] = []
        untracked: list[str] = []
        deleted: list[str] = []
        for e in st["entries"]:
            s = e["status"]
            p = e["path"]
            if s == "??":
                untracked.append(p)
            if "D" in s:
                deleted.append(p)
            if any(ch in s for ch in ("M", "A", "R", "C")):
                modified.append(p)
        return {
            "ok": True,
            "modified": sorted(set(modified)),
            "untracked": sorted(set(untracked)),
            "deleted": sorted(set(deleted)),
        }

    def diff_summary(self, root: str | Path, paths: list[str] | None = None) -> dict:
        repo = self.is_git_repo(root)
        if not repo["is_repo"]:
            return {"ok": False, "error": "not_a_git_repo"}
        stat = self._run_git(root, ["diff", "--stat"])
        names = self._run_git(root, ["diff", "--name-only"])
        details: dict[str, str] = {}
        for p in (paths or []):
            one = self._run_git(root, ["diff", "--", p])
            details[p] = one["stdout"] if one["ok"] else ""
        return {
            "ok": stat["ok"] and names["ok"],
            "stat": stat["stdout"],
            "files": [x for x in names["stdout"].splitlines() if x.strip()],
            "path_diffs": details,
        }

    def safe_files_to_commit(self, root: str | Path, allowed_paths: list[str] | None = None) -> dict:
        ch = self.changed_files(root)
        if not ch["ok"]:
            return {"ok": False, "error": ch["error"]}
        all_files = sorted(set(ch["modified"] + ch["untracked"] + ch["deleted"]))
        allowed_filter = set((allowed_paths or []))
        safe: list[str] = []
        blocked: list[str] = []
        for f in all_files:
            f_norm = f.replace("\\", "/")
            if allowed_filter and f_norm not in allowed_filter:
                continue
            if any(f_norm.startswith(pref) for pref in _UNSAFE_PREFIXES):
                blocked.append(f_norm)
            else:
                safe.append(f_norm)
        return {"ok": True, "safe_files": safe, "unsafe_to_commit": blocked}

    def validate_commit_message(self, message: str) -> dict:
        msg = (message or "").strip()
        if not msg:
            return {"ok": False, "reason": "empty_message"}
        if len(msg) > 120:
            return {"ok": False, "reason": "message_too_long"}
        if not _MSG_RE.match(msg):
            return {"ok": False, "reason": "invalid_prefix"}
        return {"ok": True, "reason": "valid"}

    def build_commit_plan(self, root: str | Path, message: str, allowed_paths: list[str] | None = None) -> dict:
        msg = self.validate_commit_message(message)
        sf = self.safe_files_to_commit(root, allowed_paths=allowed_paths)
        if not sf["ok"]:
            return {"ok": False, "error": sf["error"]}
        return {
            "ok": msg["ok"],
            "message_validation": msg,
            "message": message,
            "files": sf["safe_files"],
            "blocked_files": sf["unsafe_to_commit"],
            "will_commit": False,
        }

    def project_state(self, root: str | Path) -> dict:
        repo = self.is_git_repo(root)
        if not repo["is_repo"]:
            return {"ok": False, "is_repo": False, "status": {}, "last_commit": None}
        st = self.git_status(root)
        lg = self._run_git(root, ["log", "-1", "--oneline"])
        return {
            "ok": st["ok"],
            "is_repo": True,
            "status": st,
            "last_commit": lg["stdout"] if lg["ok"] else None,
        }

    def health(self) -> dict[str, Any]:
        return {"ok": True, "status": "ready", "module": "agent_git", "class": "AgentGitIntegration"}

    def describe(self) -> str:
        return "AgentGitIntegration"


_INSTANCE: AgentGitIntegration | None = None


def get_instance(project_root: Path | str | None = None) -> AgentGitIntegration:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentGitIntegration(project_root)
    return _INSTANCE


AgentGitFacade = AgentGitIntegration

__all__ = ["AgentGitIntegration", "AgentGitFacade", "get_instance"]
