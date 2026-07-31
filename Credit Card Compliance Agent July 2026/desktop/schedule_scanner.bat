@echo off
REM ===========================================================================
REM  Register daily_scanner.py with Windows Task Scheduler
REM
REM  Run this ONCE, from the agent folder, as Administrator.
REM  It creates a task that scrapes the nine regulator sites every weekday
REM  morning and writes changes to regulatory_updates\.
REM
REM  To remove later:  schtasks /delete /tn "ComplyLine Daily Scan" /f
REM ===========================================================================

setlocal
cd /d "%~dp0"

echo.
echo   ComplyLine - schedule the daily regulatory scan
echo   ===============================================
echo.

if not exist "daily_scanner.py" (
    echo   [X] daily_scanner.py not found in this folder.
    echo       Put this file next to daily_scanner.py.
    echo       Current folder: %CD%
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo   [X] No virtual environment. Run run.bat first.
    pause
    exit /b 1
)

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo   [X] Administrator rights required.
    echo       Right-click this file and choose "Run as administrator".
    pause
    exit /b 1
)

set TASKNAME=ComplyLine Daily Scan
set PYEXE=%CD%\.venv\Scripts\python.exe
set SCRIPT=%CD%\daily_scanner.py

echo   Task     : %TASKNAME%
echo   Runs     : weekdays at 07:00
echo   Command  : "%PYEXE%" "%SCRIPT%"
echo   Folder   : %CD%
echo.

schtasks /create ^
    /tn "%TASKNAME%" ^
    /tr "cmd /c cd /d \"%CD%\" && \"%PYEXE%\" \"%SCRIPT%\"" ^
    /sc weekly ^
    /d MON,TUE,WED,THU,FRI ^
    /st 07:00 ^
    /rl HIGHEST ^
    /f

if %errorlevel% equ 0 (
    echo.
    echo   [OK] Scheduled.
    echo.
    echo   Test it now without waiting:
    echo       schtasks /run /tn "%TASKNAME%"
    echo.
    echo   Then check regulatory_updates\ for fresh files.
    echo.
    echo   One caveat: a sleeping laptop misses its window silently. If the
    echo   scan needs to be reliable, host it instead - see
    echo   complyline\deploy\DEPLOY.md
) else (
    echo.
    echo   [X] Could not create the task. Confirm you are running as
    echo       Administrator.
)

echo.
pause
