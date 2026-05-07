@echo off
setlocal
cd /d "%~dp0"

echo Starte Backend-Watcher...
curl -s -m 2 http://127.0.0.1:5002/api/health >nul 2>nul
if %ERRORLEVEL%==0 (
  echo Backend ist bereits erreichbar auf Port 5002. Kein zweiter Start.
) else (
  start "Rainer Backend Watcher" cmd /k call "%~dp0watch-backend.bat"
)

echo Starte Frontend...
start "Rainer Frontend" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

echo.
echo Fertig. Fenster:
echo - Rainer Backend Watcher
echo - Rainer Frontend
echo.
endlocal
