from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_agent(task: str, worktree: str, run_id: str) -> int:
    logger.info("[agent_worker] run_id=%s", run_id)
    logger.info("[agent_worker] worktree=%s", worktree)
    logger.info("[agent_worker] task=%s", task)
    if worktree and os.path.isdir(worktree):
        os.chdir(worktree)
    backend_dir = os.path.dirname(__file__)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    try:
        from agent_model_router import router

        result = router.route(task, task_type="coding")
        print(result.get("text", ""))
        return 0
    except Exception as exc:
        logger.error("agent worker failed: %s", exc)
        print(f"[fallback] {task}")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rainer Agent Worker")
    parser.add_argument("--task", required=True)
    parser.add_argument("--worktree", default=".")
    parser.add_argument("--run-id", default="none")
    args = parser.parse_args()
    raise SystemExit(run_agent(args.task, args.worktree, args.run_id))
