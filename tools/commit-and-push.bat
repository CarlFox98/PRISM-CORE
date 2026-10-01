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

REM The subject used to be hardcoded to 2.0.0's headline, so every release
REM after it was committed under the wrong description. Pass one as an
REM argument, or get a plain version subject.
REM     commit-and-push.bat "2.2.2: retire the chat stopgap"
if "%~1"=="" (set "MSG=PRISM %VER%") else (set "MSG=PRISM %VER%: %~1")

echo PRISM %VER%
echo   commit subject: %MSG%
echo.

git add -A
git diff --cached --quiet
if %errorlevel%==0 (
  echo Nothing new to commit.
) else (
  git commit -m "%MSG%" -m "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_01BhZC2kXnnmGgNsAxePTeBh"
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
