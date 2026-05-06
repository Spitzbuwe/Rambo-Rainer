@echo off
setlocal
cd /d "%~dp0"
REM Wenn /api/health auf 5002 antwortet: kein zweiter Prozess
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:5002/api/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { Write-Host 'Backend laeuft bereits auf Port 5002.'; exit 0 } } catch { } ; exit 1"
if %ERRORLEVEL% equ 0 exit /b 0

echo Starte Backend auf Port 5002...
python -B backend\main.py
endlocal
