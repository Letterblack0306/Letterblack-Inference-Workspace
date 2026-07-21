@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -m backend.server --host 127.0.0.1 --port 8088
) else (
  python -m backend.server --host 127.0.0.1 --port 8088
)
endlocal
