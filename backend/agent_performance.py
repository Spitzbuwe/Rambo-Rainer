"""Performance integration orchestrator: incremental + parallel + cache."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent_caching import AgentCache
from agent_incremental import AgentIncrementalTracker
from agent_parallel import AgentParallelRunner


class AgentPerformanceOrchestrator:
    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root or ".").resolve()
        self.incremental = AgentIncrementalTracker(self.project_root)
        self.cache = AgentCache(self.project_root)
        self.parallel = AgentParallelRunner(self.project_root)

    def analyze_changes(self, root, previous_snapshot=None) -> dict:
        current = self.incremental.snapshot(root, label="current")
        if previous_snapshot is None:
            changed = sorted(current["files"].keys())
            diff = {"added": changed, "modified": [], "removed": [], "unchanged_count": 0}
        else:
            diff = self.incremental.diff(previous_snapshot, current)
            changed = sorted(set(diff["added"] + diff["modified"] + diff["removed"]))
        rec = self.incremental.recommend_checks(changed)
        return {
            "ok": True,
            "snapshot": current,
            "diff": diff,
            "changed_files": changed,
            "recommended_checks": rec,
        }

    def cached_check(self, check_name, payload, fn, ttl_seconds=None) -> dict:
        return self.cache.cached_call(
            namespace=f"check:{check_name}",
            payload=payload,
            fn=fn,
            ttl_seconds=ttl_seconds,
        )

    def recommend_and_run_checks(self, root, previous_snapshot=None, check_runner=None) -> dict:
        analysis = self.analyze_changes(root, previous_snapshot=previous_snapshot)
        checks = analysis["recommended_checks"]["checks"]
        if not checks:
            return {
                "ok": True,
                "analysis": analysis,
                "results": [],
                "skipped": True,
                "reason": "no_changes",
            }

        def _default_runner(check_name: str) -> dict:
            return {"check_name": check_name, "ok": True}

        runner = check_runner or _default_runner
        tasks = []
        for c in checks:
            tasks.append(
                {
                    "name": c,
                    "fn": lambda check=c: runner(check),
                    "metadata": {"check_name": c},
                }
            )
        run = self.parallel.run_many(tasks, max_workers=3, fail_fast=False)
        return {"ok": True, "analysis": analysis, "results": run["results"], "skipped": False}

    def performance_summary(self) -> dict:
        return {
            "cache": self.cache.stats(),
            "parallel": self.parallel.stats(),
            "incremental": self.incremental.health(),
        }

    def health(self) -> dict:
        return {
            "ok": True,
            "status": "ready",
            "module": "agent_performance",
            "cache_ok": self.cache.health()["ok"],
            "parallel_ok": self.parallel.health()["ok"],
            "incremental_ok": self.incremental.health()["ok"],
        }


_INSTANCE: AgentPerformanceOrchestrator | None = None


def get_instance(project_root: Path | str | None = None) -> AgentPerformanceOrchestrator:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = AgentPerformanceOrchestrator(project_root)
    return _INSTANCE


__all__ = ["AgentPerformanceOrchestrator", "get_instance"]
