@echo off
setlocal
cd /d "%~dp0"

python -m unittest discover -s tests -p "test_*.py"
if errorlevel 1 exit /b %errorlevel%

node scripts\env-contract-guard.js
if errorlevel 1 exit /b %errorlevel%

for /R backend %%F in (*.py) do @python -m py_compile "%%F" || exit /b 1
if errorlevel 1 exit /b %errorlevel%

for /R web\js %%F in (*.js) do @node --input-type=module --check < "%%F" || exit /b 1
if errorlevel 1 exit /b %errorlevel%

echo Letterblack Inference Workspace validation passed.
