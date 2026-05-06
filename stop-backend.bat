@echo off
setlocal
echo Beende Prozess(e) auf TCP-Port 5002 (falls vorhanden)...
powershell -NoProfile -Command ^
  "$p = Get-NetTCPConnection -LocalPort 5002 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; ^
   foreach ($pid in $p) { if ($pid) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Write-Host \"PID $pid beendet.\" } }"
endlocal
