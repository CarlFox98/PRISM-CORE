@echo off
REM ============================================================
REM  Register the PRISM weekly maintenance task with Windows.
REM  Runs silently (pythonw, no window) every Sunday at 4:00 AM.
REM  Re-run to update; run uninstall-maintenance-task.bat to remove.
REM  Edit /D and /ST below to change the day/time.
REM ============================================================
setlocal
cd /d "%~dp0"

set "TN=PRISM Weekly Maintenance"
set "PYW=%~dp0prismenv\Scripts\pythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
set "SCRIPT=%~dp0scripts\prism-maintenance.py"

schtasks /Create /TN "%TN%" /TR "\"%PYW%\" \"%SCRIPT%\"" /SC WEEKLY /D SUN /ST 04:00 /F

if %errorlevel%==0 (
  echo.
  echo [OK] Scheduled "%TN%" - every Sunday at 4:00 AM.
  echo      Logs land in maintenance-logs\. Run prism-maintenance.bat to test now.
) else (
  echo.
  echo [!] Could not create the task. If it mentions access denied, right-click
  echo     this file and "Run as administrator".
)
echo.
pause
