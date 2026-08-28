@echo off
REM ============================================================
REM  PRISM maintenance - run the weekly health check + cleanup
REM  by hand (Task Scheduler runs it silently via pythonw).
REM ============================================================
title PRISM Maintenance
cd /d "%~dp0"

REM UTF-8 so the check marks / arrows in the report render correctly
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PY=%~dp0prismenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0scripts\prism-maintenance.py" %*

echo.
pause
