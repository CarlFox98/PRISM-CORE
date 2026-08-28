@echo off
REM ============================================================
REM  PRISM -> github-pages deploy (copy + commit + push)
REM  Flattens the hosted overlays out of the source layout and
REM  pushes the separate 'streaming' repo, so the HOSTED copies
REM  can never drift from source.
REM ============================================================
title PRISM - deploy hosted overlays
cd /d "%~dp0.."

set "PY=%~dp0..\prismenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0..\scripts\deploy-pages.py"
if errorlevel 1 (
  echo.
  echo [!] Deploy failed.
  pause & exit /b 1
)

echo.
cd github-pages

git diff --quiet && git diff --cached --quiet
if %errorlevel%==0 (
  echo No changes to commit.
) else (
  git add -A
  git commit -m "sync hosted overlays with PRISM source"
)

echo.
echo Pushing the hosted overlays repo...
git push origin main

if %errorlevel%==0 (
  echo.
  echo [OK] Hosted overlays are live and match source.
) else (
  echo.
  echo [!] Push failed - see the message above.
)
echo.
pause
