@echo off
echo Stopping Letterblack server...
echo.
echo Option 1: Press Ctrl+C in the server window
echo Option 2: Kill process on port 8088
echo.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8088') do (
  echo Killing process: %%a
  taskkill /PID %%a /F 2>nul
)
echo Done.
pause