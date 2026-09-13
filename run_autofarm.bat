@echo off
REM ============================================================
REM  WorkBuddy Auto-Farm - ONE CLICK, fully automatic (portable)
REM    1. restart client with remote debugging port 9222
REM    2. wait for CDP ready
REM    3. run CDP automation (create_canvas + templates)
REM    4. run multi-account harvest (checkin+accept+claim+travel)
REM  All paths derived from this script's location - portable.
REM ============================================================
setlocal

set "WB=%LOCALAPPDATA%\Programs\WorkBuddy\WorkBuddy.exe"
set "PY=%USERPROFILE%\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
if not exist "%PY%" (
  REM fallback: first managed python version dir
  for /d %%D in ("%USERPROFILE%\.workbuddy\binaries\python\versions\*") do (
    if exist "%%D\python.exe" set "PY=%%D\python.exe"
  )
)
set "SKDIR=%~dp0"
set "SCRIPT=%SKDIR%scripts\cdp_autofarm.py"
set "HARVEST=%SKDIR%scripts\harvest.py"
set "OUT=%SKDIR%autofarm_log.txt"

if not exist "%WB%"     echo [ERROR] WorkBuddy.exe not found & pause & exit /b 1
if not exist "%PY%"     echo [ERROR] managed python not found & pause & exit /b 1
if not exist "%SCRIPT%" echo [ERROR] cdp_autofarm.py not found & pause & exit /b 1

echo ============================================================
echo  WorkBuddy Auto-Farm
echo ============================================================
echo.
echo [1/4] Restarting WorkBuddy with debug port 9222 ...
taskkill /IM WorkBuddy.exe /F >nul 2>&1
timeout /t 4 /nobreak >nul
start "" "%WB%" --remote-debugging-port=9222
echo       launched.

echo.
echo [2/4] Waiting for CDP and running UI automation (~1-2 min) ...
"%PY%" "%SCRIPT%" --wait 150 --canvas --templates 4 --shot "%SKDIR%autofarm_shot.png" > "%OUT%" 2>&1
type "%OUT%"

echo.
echo [3/4] Multi-account harvest (checkin + accept + claim + travel) ...
"%PY%" "%HARVEST%"

echo.
echo [4/4] DONE.
echo.
echo  NOTE: the client is still in DEBUG mode.
echo        Restart WorkBuddy normally when you are done.
echo.
pause
