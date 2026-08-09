@echo off
REM ============================================================
REM  PRISM maintenance - run the weekly health check + cleanup
REM  by hand (Task Scheduler runs it silently via pythonw).
REM ============================================================
title PRISM Maintenance
cd /d "%~dp0"

set "PY=%~dp0prismenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0scripts\prism-maintenance.py" %*

echo.
pause
