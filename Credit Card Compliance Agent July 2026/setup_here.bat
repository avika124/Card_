@echo off
REM ===========================================================================
REM  setup_here.bat
REM
REM  Makes THIS folder the working agent.
REM
REM  Copies the agent's source modules from your existing folder into this one,
REM  puts json_extract.py where it needs to be, and hands off to run.bat.
REM
REM  Your original folder is never modified. It stays as a fallback.
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   Credit Card Compliance Agent - July 2026
echo   Set up this folder as the working copy
echo   =========================================
echo.

REM --- Where is the existing agent? ------------------------------------------
set "DEFAULT_SRC=%USERPROFILE%\OneDrive\Documents\Claude\Projects\Credit Card Compliance Agent"

echo   Looking for your existing agent folder...
echo.

if exist "%DEFAULT_SRC%\app.py" (
    echo   Found: %DEFAULT_SRC%
    echo.
    set /p CONFIRM="   Use this folder? [Y/n]: "
    if /i "!CONFIRM!"=="n" goto :ask
    set "SRC=%DEFAULT_SRC%"
    goto :gotsrc
)

:ask
echo   Could not find app.py at the expected path.
echo.
echo   Open the folder containing app.py, click the address bar, copy the
echo   path, and paste it below.
echo.
set /p SRC="   Path: "
REM strip surrounding quotes if the user pasted them
set SRC=!SRC:"=!

if not exist "!SRC!\app.py" (
    echo.
    echo   [X] No app.py found at:
    echo       !SRC!
    echo.
    echo   That folder should contain app.py, compliance_engine.py, and the
    echo   other agent modules. If you cannot find them, look one level up
    echo   from any __pycache__ folder - Python always writes __pycache__
    echo   inside the folder holding the source it compiled.
    echo.
    pause
    exit /b 1
)

:gotsrc

REM --- Guard against copying a folder onto itself ----------------------------
if /i "!SRC!"=="%CD%" (
    echo.
    echo   [X] Source and destination are the same folder. Nothing to do.
    pause
    exit /b 1
)

echo.
echo   Source: !SRC!
echo   Target: %CD%
echo.

REM --- Copy the modules ------------------------------------------------------
echo   [1/4] Copying agent modules...

set COPIED=0
for %%f in (
    app.py
    compliance_engine.py
    consistency_checker.py
    revenue_optimizer.py
    web_scraper.py
    regulatory_monitor.py
    daily_scanner.py
    report_generator.py
    regulations.json
    requirements.txt
) do (
    if exist "!SRC!\%%f" (
        copy /y "!SRC!\%%f" "%CD%\%%f" >nul
        echo         %%f
        set /a COPIED+=1
    ) else (
        echo         [missing] %%f
    )
)

REM Anything else at the top level that we have not already handled
for %%f in ("!SRC!\*.py") do (
    if not exist "%CD%\%%~nxf" (
        copy /y "%%f" "%CD%\%%~nxf" >nul
        echo         %%~nxf  ^(extra^)
        set /a COPIED+=1
    )
)

if !COPIED! lss 5 (
    echo.
    echo   [X] Only !COPIED! files copied. That folder does not look like the
    echo       agent. Check the path and try again.
    pause
    exit /b 1
)

echo         !COPIED! files copied
echo.

REM --- Bring across existing data --------------------------------------------
echo   [2/4] Existing data...

set HASDATA=0
if exist "!SRC!\input"               set HASDATA=1
if exist "!SRC!\regulatory_updates"  set HASDATA=1
if exist "!SRC!\scraping_info"       set HASDATA=1

if !HASDATA!==1 (
    echo.
    echo         Your old folder has reference documents and/or scan history.
    echo         The consistency checker compares against these - without them
    echo         it finds no conflicts and says nothing about why.
    echo.
    set /p COPYDATA="        Copy them across? [Y/n]: "
    if /i not "!COPYDATA!"=="n" (
        for %%d in (input regulatory_updates scraping_info alerts) do (
            if exist "!SRC!\%%d" (
                robocopy "!SRC!\%%d" "%CD%\%%d" /E /NFL /NDL /NJH /NJS /NC /NS >nul
                echo         %%d\
            )
        )
    )
) else (
    echo         None found - starting clean
)
echo.

REM --- API key ---------------------------------------------------------------
echo   [3/4] API key...

if exist "!SRC!\.env" (
    if not exist "%CD%\.env" (
        copy /y "!SRC!\.env" "%CD%\.env" >nul
        echo         Copied .env from the old folder
    ) else (
        echo         .env already here - keeping it
    )
) else (
    echo         No .env in the old folder - run.bat will ask for your key
)
echo.

REM --- Patch placement -------------------------------------------------------
echo   [4/4] Patches...

if exist "patches\json_extract.py" (
    copy /y "patches\json_extract.py" "%CD%\json_extract.py" >nul
    echo         json_extract.py placed at the top level
)
if exist "patches\revenue_optimizer_patch.py" (
    copy /y "patches\revenue_optimizer_patch.py" "%CD%\revenue_optimizer_patch.py" >nul
    echo         revenue_optimizer_patch.py placed at the top level
)
if exist "desktop\run.bat"              copy /y "desktop\run.bat" "%CD%\run.bat" >nul
if exist "desktop\schedule_scanner.bat" copy /y "desktop\schedule_scanner.bat" "%CD%\schedule_scanner.bat" >nul
echo         run.bat and schedule_scanner.bat placed at the top level
echo.

REM --- Is the parse fix applied? ---------------------------------------------
findstr /c:"```(?:json)?" compliance_engine.py >nul 2>&1
if !errorlevel! equ 0 (
    echo   ------------------------------------------------------------------
    echo   STILL TO DO: compliance_engine.py uses the fenced-only JSON regex.
    echo   Until that is changed, the A1-J checklist contributes nothing to
    echo   your reports and the failure is silent.
    echo.
    echo   Two lines, two files. See patches\INTEGRATION.md
    echo   ------------------------------------------------------------------
    echo.
)

echo   Setup complete. This folder is now the working agent.
echo   Your original folder was not modified.
echo.
set /p LAUNCH="   Launch now? [Y/n]: "
if /i "!LAUNCH!"=="n" (
    echo.
    echo   Start it later by double-clicking run.bat
    echo.
    pause
    exit /b 0
)

call run.bat
