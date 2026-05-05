from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


class IssueTrackerFacade:
    __slots__ = ("project_root",)

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()

    def _run_git(self, args: list[str]) -> dict[str, Any]:
        try:
            cp = subprocess.run(
                ["git", *args],
                cwd=str(self.project_root),
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
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "returncode": -1, "stdout": "", "stderr": str(exc)}

    def list_issues(self, repo: str | None = None, limit: int = 20) -> dict[str, Any]:
        # Local-safe placeholder: surfaces git todo/fix markers as issue-like hints.
        files = self._run_git(["ls-files"])
        if not files.get("ok"):
            return {"ok": False, "error": "not_a_git_repo", "issues": []}
        issues: list[dict[str, Any]] = []
        for path in (files.get("stdout") or "").splitlines():
            if len(issues) >= max(1, min(limit, 100)):
                break
            if path.startswith(("node_modules/", ".git/", "dist/", "build/")):
                continue
            full = self.project_root / path
            if not full.exists() or not full.is_file():
                continue
            try:
                content = full.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if "TODO" in content or "FIXME" in content:
                issues.append(
                    {
                        "id": f"local-{len(issues) + 1}",
                        "title": f"Review markers in {path}",
                        "state": "open",
                        "source": "local_scan",
                        "repo": repo or "local",
                    }
                )
        return {"ok": True, "issues": issues, "count": len(issues)}

    def create_issue(self, title: str, body: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "issue": {
                "id": f"draft-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "title": title.strip() or "Untitled",
                "body": body or "",
                "state": "draft",
                "created": False,
                "requires_manual_submit": True,
            },
        }

    def create_pr(self, branch: str, base: str, title: str, body: str = "") -> dict[str, Any]:
        return {
            "ok": True,
            "pr": {
                "number": None,
                "branch": branch,
                "base": base,
                "title": title.strip() or f"Update {branch}",
                "body": body or "",
                "state": "draft",
                "created": False,
                "requires_manual_submit": True,
            },
        }

    def get_pr_diff(self, pr_number: int | str) -> dict[str, Any]:
        diff = self._run_git(["diff", "--stat"])
        return {"ok": bool(diff.get("ok")), "pr_number": pr_number, "diff_stat": diff.get("stdout", "")}

    def post_pr_review(self, pr_number: int | str, comment: str) -> dict[str, Any]:
        return {"ok": True, "pr_number": pr_number, "comment": comment or "", "posted": False, "mode": "local_draft"}

    def health(self) -> dict[str, Any]:
        return {"module": "agent_issue_tracker", "class": "IssueTrackerFacade", "ok": True}

    def describe(self) -> str:
        return "Issue/PR facade (local-safe draft mode)"


_INSTANCE: IssueTrackerFacade | None = None


def get_instance(project_root: Path | str | None = None) -> IssueTrackerFacade:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = IssueTrackerFacade(project_root)
    return _INSTANCE


__all__ = ["IssueTrackerFacade", "get_instance"]
