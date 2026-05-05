"""Agent Run Retry Loop — Level 8.2.

Wraps the step engine with a controlled retry/repair loop.
On test failure, triggers the error fixer and re-runs up to MAX_RETRIES times.
No auto-apply, no auto-commit, no auto-rollback.
"""
from __future__ import annotations

from typing import Optional

MAX_RETRIES: int = 2


class RetryLoopController:
    """
    Runs the StepEngineAgent with automatic repair-and-retry on test failure.

    Rules:
    - Read/analyze retries are allowed (up to MAX_RETRIES)
    - No automatic write / apply at any retry stage
    - Each repair attempt uses the error_fixer's build_fix_plan output
    - Returns retry_count, repaired flag, and the final step result
    """

    def __init__(
        self,
        step_engine,
        error_fixer,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.step_engine = step_engine
        self.error_fixer = error_fixer
        self.max_retries = int(max_retries)

    def run_with_retry(
        self,
        *,
        task: str,
        path: str,
        current_content: str,
        proposed_content: str,
        run_checks: bool = True,
    ) -> dict:
        """
        Run step flow with automatic retry on test failure.

        Returns a dict with:
        - ok, stage, result (final step result)
        - retry_count
        - repaired (True if at least one repair cycle was performed)
        - max_retries_reached
        - repair_history (list of repair attempts)
        - writes_files: always False
        - auto_apply: always False
        """
        retry_count = 0
        repaired = False
        repair_history: list[dict] = []
        working_content = str(proposed_content)

        while True:
            result = self.step_engine.run_step_flow(
                task=task,
                path=path,
                current_content=current_content,
                proposed_content=working_content,
                confirmed=False,
                run_checks=run_checks,
            )

            stage = str(result.get("stage") or "unknown")
            test_result = result.get("test_runner_result")
            test_failed = stage == "test_failed" or (
                test_result and not bool(test_result.get("ok"))
            )

            if not test_failed or retry_count >= self.max_retries:
                max_retries_reached = test_failed and retry_count >= self.max_retries
                return {
                    "ok": bool(result.get("ok")),
                    "stage": stage,
                    "result": result,
                    "retry_count": retry_count,
                    "repaired": repaired,
                    "max_retries_reached": max_retries_reached,
                    "repair_history": repair_history,
                    "writes_files": False,
                    "auto_apply": False,
                    "auto_commit": False,
                    "auto_rollback": False,
                }

            # Build repair plan and adjust working content
            tr = test_result or {}
            repair = self.error_fixer.build_fix_plan(
                check_name=str(tr.get("check") or "test_runner"),
                returncode=int(tr.get("returncode") or 1),
                stdout=str(tr.get("stdout") or ""),
                stderr=str(tr.get("stderr") or ""),
            )

            # Apply a minimal repair hint to the proposed content
            repaired_content = _apply_repair_hint(
                working_content, repair, retry_count
            )

            repair_history.append(
                {
                    "attempt": retry_count + 1,
                    "check": str(tr.get("check") or "—"),
                    "error_category": str(repair.get("error_category") or "—"),
                    "repair_strategy": str(repair.get("step_engine_next_action") or "—"),
                }
            )

            working_content = repaired_content
            retry_count += 1
            repaired = True


def _apply_repair_hint(content: str, repair: dict, attempt: int) -> str:
    """
    Minimal content repair: appends a repair hint comment at the end.
    In a real implementation this would apply the structured repair_plan diffs.
    For Level 8.2 the contract is: retry happens, content is updated, writes=False.
    """
    hint = str(repair.get("step_engine_next_action") or "repair_required")
    marker = f"# repair_attempt={attempt + 1} action={hint}"
    lines = content.splitlines()
    # Replace an existing repair marker or append
    lines = [l for l in lines if not l.strip().startswith("# repair_attempt=")]
    lines.append(marker)
    return "\n".join(lines)


__all__ = ["RetryLoopController", "MAX_RETRIES"]
