$ErrorActionPreference = "Stop"

Write-Host "Eval Regression Suite" -ForegroundColor Cyan
python -m pytest backend/tests/test_eval_regression_suite.py backend/tests/test_quality_autofix_eval.py -q
if ($LASTEXITCODE -ne 0) { exit 10 }

Write-Host "Eval regression passed" -ForegroundColor Green
exit 0
