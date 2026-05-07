@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo Backend-Watcher gestartet (Port 5002).
echo Bei Absturz wird backend\main.py automatisch neu gestartet.
echo Beenden mit Ctrl+C.
echo.

:loop
echo [%date% %time%] Starte Backend...
python -B backend\main.py
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] Backend beendet mit ExitCode !EXITCODE!.
if "!EXITCODE!"=="3" (
  echo [%date% %time%] Backend bereits aktiv auf Port 5002. Kein Neustart durch Watcher.
  timeout /t 5 /nobreak >nul
  goto loop
)
echo Neustart in 3 Sekunden...
timeout /t 3 /nobreak >nul
goto loop
