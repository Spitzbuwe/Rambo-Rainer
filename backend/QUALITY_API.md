# Quality API Quick Guide

## Endpoints
- `POST /api/quality/autofix-run`: Runs checks, optional auto-fix, optional `eval_after`.
- `POST /api/quality/eval-suite`: Runs eval suite and can attach score to task graph.
- `GET /api/quality/eval-history`: Recent eval runs.
- `GET /api/quality/task-graph`: Recent autofix/task graph entries.

## Autofix Run (recommended)
Request example:
```json
{
  "task": "Quality gate: Checks stabilisieren, danach Eval",
  "checks": ["python -m py_compile backend/main.py", "python -m pytest tests -q"],
  "auto_fix": true,
  "max_fix_rounds": 2,
  "eval_after": true,
  "eval_quick": true,
  "skip_eval_on_check_fail": true
}
```

Response includes:
- `run_id`: Stable id for this autofix run.
- `checks_ok`: `true` when final checks are green.
- `task_graph`: persisted row (with eval fields if available).

## Attach Eval To Exact Run
`POST /api/quality/eval-suite` supports:
- `attach_eval_to_latest_graph: true`
- `attach_run_id: "quality_..."`

When `attach_run_id` is provided, backend attaches eval score to that exact task-graph row first, then falls back to latest-row heuristic only if needed.

## Runbook: Autofix + Eval
1. Start backend and verify `GET /api/health`.
2. Call `POST /api/quality/autofix-run` with `eval_after=true`.
3. If needed, run `POST /api/quality/eval-suite` with `attach_run_id` from step 2.
4. Inspect `GET /api/quality/task-graph?limit=5` and `GET /api/quality/eval-history?limit=5`.

## Follow-up
- PR-enablement update: branch includes post-merge validation note for run_id attach flow.
