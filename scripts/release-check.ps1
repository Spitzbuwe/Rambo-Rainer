$ErrorActionPreference = "Stop"

Write-Host "Release Check: targeted quality + connectivity tests" -ForegroundColor Cyan
python -m pytest backend/tests/test_quality_autofix_eval.py backend/tests/test_connectivity_chat_fallback.py -q
if ($LASTEXITCODE -ne 0) { exit 10 }

Write-Host "Release Check: backend syntax" -ForegroundColor Cyan
python -m py_compile backend/main.py
if ($LASTEXITCODE -ne 0) { exit 20 }

Write-Host "Release check passed" -ForegroundColor Green
exit 0
