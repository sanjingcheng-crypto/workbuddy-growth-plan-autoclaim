@echo off
REM ============================================================
REM  WorkBuddy Debug Launcher (portable)
REM  - restarts WorkBuddy with remote debugging port 9222
REM  - enables CDP automation (cdp_autofarm.py / wb_cdp.py)
REM  Located in the skill dir; works for any Windows user.
REM ============================================================
setlocal

set "WB=%LOCALAPPDATA%\Programs\WorkBuddy\WorkBuddy.exe"
set "PORT=9222"

if not exist "%WB%" (
  echo [ERROR] WorkBuddy.exe not found at:
  echo         %WB%
  echo.
  pause
  exit /b 1
)

echo ============================================================
echo  WorkBuddy Debug Launcher
echo ============================================================
echo.

echo [1/3] Closing running WorkBuddy processes ...
taskkill /IM WorkBuddy.exe /F >nul 2>&1
timeout /t 3 /nobreak >nul
echo       done.

echo.
echo [2/3] Starting WorkBuddy with remote debugging on port %PORT% ...
start "" "%WB%" --remote-debugging-port=%PORT% --enable-logging
if errorlevel 1 (
  echo       [ERROR] failed to start WorkBuddy.exe
  pause
  exit /b 1
)
timeout /t 6 /nobreak >nul

echo.
echo [3/3] Checking debug endpoint ...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 6 'http://127.0.0.1:%PORT%/json/version'; if ($r.StatusCode -eq 200) { Write-Host '      OK - debug endpoint is UP' } else { Write-Host '      [WARN] status' $r.StatusCode } } catch { Write-Host '      [WARN] debug endpoint not responding yet' }"

echo.
echo ============================================================
echo  DONE. WorkBuddy is running in DEBUG mode.
echo.
echo  Next: run cdp_autofarm.py --canvas / --templates
echo  When finished, restart WorkBuddy normally to close the port.
echo ============================================================
echo.
pause
