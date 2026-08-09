@echo off
REM ============================================================
REM  PRISM - refresh prism-followers.json from Twitch
REM  Uses your stream-manager Twitch token + app credentials.
REM  Requires the token to include the moderator:read:followers
REM  scope (re-authorize stream-manager once if it doesn't).
REM ============================================================
title PRISM - refresh followers
cd /d "%~dp0"

REM your stream-manager checkout (holds the cached token + .env)
set "SM=C:\Users\NeoTheFox98\Desktop\Streaming\stream-manager-main\stream-manager-main"

set "PY=%~dp0prismenv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" "%~dp0scripts\refresh-followers.py" ^
  --token "%SM%\.twitch_user_token.json" ^
  --env   "%SM%\.env" ^
  --out   "%~dp0prism-followers.json"

echo.
pause
