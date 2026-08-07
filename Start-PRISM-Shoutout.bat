@echo off
REM ============================================================
REM  PRISM Shoutout - one-click launcher
REM  Double-click this to start the shoutout service.
REM  Keep the window open while you stream; close it to stop.
REM ============================================================
title PRISM Shoutout Service
cd /d "%~dp0"

set "PY=%~dp0prismenv\Scripts\python.exe"

if not exist "%PY%" (
  echo.
  echo [!] Couldn't find the virtual environment at:
  echo     %PY%
  echo.
  echo     Create it once with:
  echo       py -m venv prismenv
  echo       prismenv\Scripts\python.exe -m pip install websockets requests
  echo.
  pause
  exit /b 1
)

echo Starting PRISM Shoutout service...
echo (Leave this window open. Close it to stop.)
echo.
"%PY%" "%~dp0prism_shoutout_service.py"

echo.
echo Service stopped.
pause
