@echo off
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
 echo Python nao encontrado. Instale Python 3.11+ e inclua no PATH.
 pause
 exit /b 1
)
echo CT Pulse - servidor local. Para iniciar com dados ficticios, execute python server.py demo uma unica vez no PowerShell.
python server.py serve --host 0.0.0.0 --port 8000
pause
