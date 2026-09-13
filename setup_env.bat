@echo off
REM ============================================================
REM  WorkBuddy Growth AutoClaim - fresh machine environment setup
REM  Creates managed venv + installs playwright/urllib3 + chromium.
REM  All paths derived from %USERPROFILE% - portable across users.
REM  Run ONCE after copying this skill to a new computer.
REM ============================================================
setlocal

set "WBD=%USERPROFILE%\.workbuddy"
set "PY="
REM 1) managed python version (shipped with WorkBuddy desktop)
for /d %%D in ("%WBD%\binaries\python\versions\*") do (
  if exist "%%D\python.exe" set "PY=%%D\python.exe"
)
if not defined PY (
  where python >nul 2>&1 && set "PY=python" || (echo [ERROR] Python not found & pause & exit /b 1)
)
echo [setup] Python: %PY%

REM 2) venv (reuse the managed env path if present, else create)
set "VENV=%WBD%\binaries\python\envs\default"
if not exist "%VENV%\Scripts\python.exe" (
  echo [setup] Creating venv: %VENV%
  "%PY%" -m venv "%VENV%"
)
set "VPY=%VENV%\Scripts\python.exe"

REM 3) deps
echo [setup] Installing playwright / urllib3 ...
"%VPY%" -m pip install --quiet --upgrade pip
"%VPY%" -m pip install --quiet playwright urllib3

REM 4) chromium (only needed for CDP UI automation)
echo [setup] Installing chromium browser (needed for CDP) ...
"%VPY%" -m playwright install chromium

echo.
echo [OK] Environment ready.
echo      Next: double-click start_workbuddy_debug.bat (CDP) or run_autofarm.bat (full auto).
echo.
pause
