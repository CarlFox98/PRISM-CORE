@echo off
REM ============================================================
REM  PRISM -> github-pages deploy
REM  Copies the canonical overlays into the github-pages\ folder
REM  so the HOSTED copies never drift from the source of truth.
REM  Run this after editing any hosted overlay, then push the
REM  separate 'streaming' repo (instructions printed at the end).
REM ============================================================
cd /d "%~dp0"

if not exist "github-pages\" (
  echo [!] github-pages\ folder not found next to this script.
  pause & exit /b 1
)

copy /Y "prism-nowplaying.html" "github-pages\index.html"        >nul && echo  index.html          ^<- prism-nowplaying.html
copy /Y "prism-shoutout.html"   "github-pages\prism-shoutout.html" >nul && echo  prism-shoutout.html ^<- prism-shoutout.html
copy /Y "prism-thank-you.html"  "github-pages\prism-thank-you.html" >nul && echo  prism-thank-you.html^<- prism-thank-you.html
copy /Y "prism-followers.json"  "github-pages\prism-followers.json" >nul && echo  prism-followers.json^<- prism-followers.json

echo.
echo Deployed canonical overlays into github-pages\.
echo Next:  cd github-pages  ^&^&  git add -A  ^&^&  git commit -m "sync overlays"  ^&^&  git push
echo.
pause
