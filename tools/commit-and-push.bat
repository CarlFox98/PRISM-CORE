@echo off
REM ============================================================
REM  PRISM -> commit everything and push to GitHub
REM  Stages all changes (gitignore still applies: secrets, logs,
REM  github-pages\ and prismenv\ are never included), commits them
REM  as the version in VERSION, and pushes main to origin.
REM  The secret-scan pre-commit hook still runs and can block it.
REM ============================================================
title PRISM - commit and push
cd /d "%~dp0.."
set /p VER=<VERSION
echo PRISM %VER%
echo.

findstr /c:"prism_shoutout_service" ".github\workflows\ci.yml" >nul 2>&1
if %errorlevel%==0 (
  echo [!] .github\workflows\ci.yml is still the old one - GitHub checks will keep failing
  echo     until you replace it. Committing everything else anyway.
  echo.
)

git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo Nothing new to commit.
) else (
  git commit -m "PRISM %VER%: Signal + Soft Holo scene sets, themed shoutout and now-playing" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01BhZC2kXnnmGgNsAxePTeBh"
  if errorlevel 1 goto fail
)

echo.
echo Pushing... (if a GitHub login window appears, complete it yourself)
git push -u origin main
if errorlevel 1 goto fail

echo.
echo [OK] PRISM %VER% is on GitHub.
echo.
pause
exit /b 0

:fail
echo.
echo [!] Stopped - see the message above. Nothing was force-pushed.
echo.
pause
exit /b 1
