@echo off
setlocal
cd /d "%~dp0"
echo === Letterblack Inference Workspace validation ===
echo.
node scripts\validate-chain.mjs --log
exit /b %errorlevel%

