from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from agent_context_builder import ContextBuilderAgent
from agent_error_fixer import ErrorFixerAgent
from agent_patch_generator import PatchGeneratorAgent
from agent_patch_validator import PatchValidatorAgent
from agent_task_planner import TaskPlannerAgent
from agent_test_runner import TestRunnerAgent


class StepEngineAgent:
    __test__ = False

    def __init__(
        self,
        planner: TaskPlannerAgent,
        context_builder: ContextBuilderAgent,
        patch_generator: PatchGeneratorAgent,
        patch_validator: PatchValidatorAgent,
        error_fixer: ErrorFixerAgent,
        test_runner: TestRunnerAgent,
    ):
        self.planner = planner
        self.context_builder = context_builder
        self.patch_generator = patch_generator
        self.patch_validator = patch_validator
        self.error_fixer = error_fixer
        self.test_runner = test_runner

    def run_step_flow(
        self,
        *,
        task: str,
        path: str,
        current_content: str,
        proposed_content: str,
        confirmed: bool = False,
        run_checks: bool = False,
    ) -> dict[str, object]:
        text = str(task or "").strip()
        rel_path = str(path or "").strip()
        run_id = f"se_{uuid4().hex[:12]}"
        if not text:
            return {"ok": False, "status": "invalid_input", "errors": ["task_missing"]}
        if not rel_path:
            return {"ok": False, "status": "invalid_input", "errors": ["path_missing"]}

        plan = self.planner.build_plan(text, risk="medium")
        if not plan.get("ok"):
            return {"ok": False, "status": "plan_failed", "errors": [str(plan.get("error") or "plan_failed")]}

        context = self.context_builder.build_context(text, limit=4, max_chars_per_file=2000)
        if not context.get("ok"):
            return {"ok": False, "status": "context_failed", "errors": [str(context.get("error") or "context_failed")]}

        patch = self.patch_generator.generate_patch(rel_path, current_content, proposed_content)
        if not patch.get("ok"):
            return {"ok": False, "status": "patch_generate_failed", "errors": [str(patch.get("error") or "patch_generate_failed")]}

        validate = self.patch_validator.validate_patch(
            rel_path=rel_path,
            current_content=current_content,
            proposed_content=proposed_content,
            diff_text=str(patch.get("diff") or ""),
        )
        if not validate.get("ok"):
            return {"ok": False, "status": "patch_validate_failed", "errors": [str(validate.get("error") or "patch_validate_failed")]}

        stage = "validated"
        next_action = "run_required_checks"
        repair_plan = None
        test_result = None

        if str(validate.get("status")) == "large_patch_blocked":
            stage = "blocked"
            next_action = "split_patch"
            repair_plan = self.error_fixer.build_fix_plan(
                check_name="patch_validate",
                returncode=1,
                stderr="Patch überschreitet sichere Diff-Schwelle.",
            )
            next_action = str(repair_plan.get("step_engine_next_action") or next_action)
        else:
            # Integrate test-runner output directly in step flow (optional in higher-level controllers).
            rec = self.test_runner.recommend_checks(task=text, files=[rel_path])
            checks = list(rec.get("recommended_checks") or [])
            if checks and run_checks:
                test_result = self.test_runner.run_allowed_check(checks[0])
                if not bool(test_result.get("ok")):
                    stage = "test_failed"
                    next_action = "prepare_repair_patch"
                    repair_plan = self.error_fixer.build_fix_plan(
                        check_name=str(test_result.get("check") or checks[0]),
                        returncode=int(test_result.get("returncode") or 1),
                        stdout=str(test_result.get("stdout") or ""),
                        stderr=str(test_result.get("stderr") or ""),
                    )
                else:
                    next_action = "confirm_apply_handoff" if confirmed else "await_user_confirmation"
            elif checks:
                next_action = "run_recommended_checks"

        return {
            "ok": True,
            "mode": "step_engine",
            "stage": stage,
            "run_id": run_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "task": text,
            "path": rel_path.replace("\\", "/"),
            "writes_files": False,
            "auto_apply": False,
            "auto_commit": False,
            "auto_rollback": False,
            "plan": {
                "focus": plan.get("focus"),
                "risk": plan.get("risk"),
                "step_count": plan.get("step_count"),
                "steps": plan.get("steps"),
            },
            "context": {
                "selected_files": context.get("selected_files", []),
                "file_count": context.get("file_count", 0),
                "reads_all_files": False,
            },
            "patch_preview": {
                "has_changes": bool(patch.get("has_changes")),
                "diff": patch.get("diff", ""),
            },
            "validation": validate,
            "test_runner_result": test_result,
            "recommended_checks": self.test_runner.recommend_checks(task=text, files=[rel_path]).get("recommended_checks", []),
            "repair_plan": repair_plan,
            "confirm_apply_handoff": {
                "enabled": bool(confirmed and stage == "validated"),
                "target_endpoint": "/api/direct-confirm",
                "requires_confirmation": True,
                "note": "Nur nach expliziter Bestätigung; kein Auto-Apply.",
            },
            "next_action": next_action,
            "pipeline": ["plan", "context", "patch_generate", "patch_validate", "test_runner", "error_fixer_if_needed", "confirm_apply_handoff"],
            "notes": "Step Engine liefert nur Plan/Preview und schreibt nicht blind.",
        }
