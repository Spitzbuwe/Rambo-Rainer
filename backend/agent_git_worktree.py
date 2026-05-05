from __future__ import annotations

import os
import subprocess
from pathlib import Path

RUNS_SUBDIR = ".rainer_runs"


def _git(args: list[str], cwd: str) -> str:
    cp = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, shell=False)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or "").strip() or f"git {' '.join(args)} failed")
    return (cp.stdout or "").strip()


def _ensure_git_repo(project_root: str) -> None:
    if not Path(project_root, ".git").exists():
        raise ValueError(f"Kein Git-Repository: {project_root}")


def _runs_dir(project_root: str) -> str:
    return str(Path(project_root) / RUNS_SUBDIR)


def list_worktrees(project_root: str) -> list[dict]:
    try:
        _ensure_git_repo(project_root)
        out = _git(["worktree", "list", "--porcelain"], cwd=project_root)
    except Exception:
        return []
    rows = []
    cur = {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                rows.append(cur)
            p = line.split(" ", 1)[1]
            rid = Path(p).name if RUNS_SUBDIR in p else None
            cur = {"path": p, "run_id": rid, "is_agent_run": bool(rid)}
        elif line.startswith("branch "):
            cur["branch"] = line.split(" ", 1)[1].replace("refs/heads/", "")
        elif line.startswith("HEAD "):
            cur["head"] = line.split(" ", 1)[1]
    if cur:
        rows.append(cur)
    return rows


def create_worktree(run_id: str, project_root: str, base_branch: str | None = None) -> dict:
    _ensure_git_repo(project_root)
    if not base_branch:
        try:
            base_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project_root)
        except Exception:
            base_branch = "main"
    branch = f"agent/{run_id}"
    wt_path = str(Path(_runs_dir(project_root)) / run_id)
    for wt in list_worktrees(project_root):
        if wt.get("run_id") == run_id:
            return {"status": "already_exists", "run_id": run_id, "worktree_path": wt.get("path"), "branch": wt.get("branch"), "writes_files": False}
    os.makedirs(_runs_dir(project_root), exist_ok=True)
    _git(["worktree", "add", wt_path, "-b", branch, base_branch], cwd=project_root)
    return {"status": "created", "run_id": run_id, "worktree_path": wt_path, "branch": branch, "base_branch": base_branch, "writes_files": False}

