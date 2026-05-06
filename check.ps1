$ErrorActionPreference = "Stop"

$reportPath = Join-Path $PSScriptRoot "check-report.txt"
$exitCode = 0

function Write-ReportLine([string]$Line) {
    Add-Content -Path $reportPath -Value $Line
}

if (Test-Path $reportPath) { Remove-Item $reportPath -Force }
Write-ReportLine ("check.ps1 started: " + (Get-Date).ToString("o"))

Write-Host "Running stable checks (without .pyc write)..." -ForegroundColor Cyan
$env:PYTHONDONTWRITEBYTECODE = "1"

Write-Host "1) Python tests" -ForegroundColor Yellow
try {
    python -m pytest `
        backend/tests/test_unsafe_large_rewrite_payload.py `
        backend/tests/test_agent_loop_large_file_read.py `
        backend/tests/test_image_generate.py `
        backend/tests/test_prompt_routing_phase1.py `
        backend/tests/test_agent_loop_instruction_guard.py `
        backend/tests/test_direct_run_project_read.py `
        -q
    if ($LASTEXITCODE -ne 0) { $script:exitCode = 10; Write-ReportLine "pytest failed exit=$LASTEXITCODE" }
} catch {
    $script:exitCode = 10
    Write-ReportLine "pytest exception: $_"
    throw
}

Write-Host "2) Frontend unit tests (vitest)" -ForegroundColor Yellow
Push-Location frontend
try {
    npx vitest run src/utils/imageIntentParser.test.js
    if ($LASTEXITCODE -ne 0) { $script:exitCode = 20; Write-ReportLine "vitest failed exit=$LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "3) Frontend build (mit Retry)" -ForegroundColor Yellow
Push-Location frontend
try {
    $attempt = 0
    $max = 3
    $buildOk = $false
    while ($attempt -lt $max -and -not $buildOk) {
        $attempt++
        npm run build
        if ($LASTEXITCODE -eq 0) {
            $buildOk = $true
        } else {
            Write-ReportLine "npm run build failed attempt $attempt exit=$LASTEXITCODE"
            if ($attempt -lt $max) { Start-Sleep -Seconds 2 }
        }
    }
    if (-not $buildOk) { $script:exitCode = 30 }
} finally {
    Pop-Location
}

if ($exitCode -eq 0) {
    Write-ReportLine "all steps ok"
    Write-Host "All checks passed." -ForegroundColor Green
} else {
    Write-ReportLine "finished with exitCode=$exitCode"
    Write-Host "Checks finished with errors (see check-report.txt). Exit $exitCode" -ForegroundColor Red
}
exit $exitCode
