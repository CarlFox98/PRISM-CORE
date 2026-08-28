@echo off
REM Remove the PRISM weekly maintenance scheduled task.
setlocal
set "TN=PRISM Weekly Maintenance"
schtasks /Delete /TN "%TN%" /F
if %errorlevel%==0 (echo [OK] Removed "%TN%".) else (echo [!] Task not found or could not be removed.)
echo.
pause
