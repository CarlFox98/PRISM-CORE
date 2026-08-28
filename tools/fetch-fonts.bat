@echo off
REM ============================================================
REM  PRISM - download fonts locally (offline overlays)
REM  Downloads the woff2 files into fonts\ and rewrites
REM  fonts\prism-fonts.css to use them. Run once; then commit
REM  the fonts\ folder.
REM ============================================================
title PRISM - fetch fonts
cd /d "%~dp0.."

set "PY=%~dp0..\prismenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0..\scripts\fetch-fonts.py"

echo.
pause
