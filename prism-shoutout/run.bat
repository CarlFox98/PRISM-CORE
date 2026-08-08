@echo off
REM ============================================================
REM  PRISM Shoutout - run from the repo folder.
REM  Uses whatever "python" is on PATH (or a local .venv if present).
REM  Keep this window open while you stream; close it to stop.
REM ============================================================
title PRISM Shoutout Service
cd /d "%~dp0"

REM UTF-8 so the PRISM banner / box-drawing / glyphs render correctly.
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PRISM_FORCE_COLOR=1"

REM secrets live in the repo's git-ignored prismenv folder (one level up)
if not defined PRISM_SECRETS set "PRISM_SECRETS=%~dp0..\prismenv\prism-secrets.json"

if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo Starting PRISM Shoutout service...
echo (Leave this window open. Close it to stop.)
echo.
"%PY%" -m prism_shoutout

echo.
echo Service stopped.
pause
