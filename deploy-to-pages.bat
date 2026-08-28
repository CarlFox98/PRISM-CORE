@echo off
REM ============================================================
REM  PRISM -> github-pages deploy (copy + commit + push)
REM  Copies the canonical overlays into github-pages\ and pushes
REM  the separate 'streaming' repo, so the HOSTED copies can
REM  never drift from the source of truth.
REM  Run this after editing any hosted overlay.
REM ============================================================
title PRISM - deploy hosted overlays
cd /d "%~dp0"

if not exist "github-pages\" (
  echo [!] github-pages\ folder not found next to this script.
  pause & exit /b 1
)

copy /Y "prism-nowplaying.html" "github-pages\index.html"           >nul && echo  index.html           ^<- prism-nowplaying.html
copy /Y "prism-shoutout.html"   "github-pages\prism-shoutout.html"  >nul && echo  prism-shoutout.html  ^<- prism-shoutout.html
copy /Y "prism-thank-you.html"  "github-pages\prism-thank-you.html" >nul && echo  prism-thank-you.html ^<- prism-thank-you.html
copy /Y "prism-followers.json"  "github-pages\prism-followers.json" >nul && echo  prism-followers.json ^<- prism-followers.json

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
