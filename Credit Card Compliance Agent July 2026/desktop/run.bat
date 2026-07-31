@echo off
REM ===========================================================================
REM  Credit Card Compliance Agent - Windows launcher
REM
REM  Put this file in the same folder as app.py, then double-click it.
REM
REM  Handles: Python version selection, virtual environment, dependencies,
REM  data folders, and the API key. Safe to run repeatedly - it skips whatever
REM  is already done.
REM ===========================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo   Credit Card Compliance Agent
echo   ============================
echo.

REM --- Confirm we are in the right folder ------------------------------------
if not exist "app.py" (
    echo   [X] app.py not found in this folder.
    echo.
    echo       Put run.bat next to app.py, compliance_engine.py, and the rest
    echo       of the agent. Current folder:
    echo       %CD%
    echo.
    pause
    exit /b 1
)

REM --- Pick a Python ---------------------------------------------------------
REM  3.11 is the target. The agent has been compiled under 3.10 and 3.14;
REM  3.14 is too new for several dependencies and will fail on install.

set PYCMD=

py -3.11 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYCMD=py -3.11
    goto :found
)

py -3.12 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYCMD=py -3.12
    goto :found
)

py -3.10 --version >nul 2>&1
if !errorlevel! equ 0 (
    set PYCMD=py -3.10
    goto :found
)

python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
    echo   [!] Using default Python !PYVER!
    echo       If this is 3.13 or newer, dependencies may fail to install.
    echo       Install 3.11 from python.org if that happens.
    echo.
    set PYCMD=python
    goto :found
)

echo   [X] No Python found.
echo.
echo       Install Python 3.11 from:
echo       https://www.python.org/downloads/release/python-3119/
echo.
echo       During install, tick "Add python.exe to PATH".
echo.
pause
exit /b 1

:found
for /f "tokens=*" %%v in ('!PYCMD! --version 2^>^&1') do echo   [1/5] %%v
echo.

REM --- Virtual environment ---------------------------------------------------
REM  Keeps the agent's dependencies away from anything else on the machine,
REM  and pins it to the interpreter chosen above.

if not exist ".venv\Scripts\python.exe" (
    echo   [2/5] Creating virtual environment...
    !PYCMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo   [X] Could not create the virtual environment.
        pause
        exit /b 1
    )
) else (
    echo   [2/5] Virtual environment found
)

set VPY=.venv\Scripts\python.exe

REM --- Dependencies ----------------------------------------------------------
echo   [3/5] Checking dependencies...

%VPY% -c "import streamlit, anthropic, docx, bs4" >nul 2>&1
if !errorlevel! neq 0 (
    echo         Installing - this takes a few minutes the first time.
    echo.
    %VPY% -m pip install --upgrade pip --quiet
    if exist "requirements.txt" (
        %VPY% -m pip install -r requirements.txt
    ) else (
        %VPY% -m pip install streamlit anthropic python-docx python-dotenv requests beautifulsoup4 pymupdf openpyxl
    )
    if !errorlevel! neq 0 (
        echo.
        echo   [X] Dependency install failed.
        echo       Most common cause: Python 3.13+ has no wheels for some of
        echo       these yet. Install Python 3.11 and delete the .venv folder,
        echo       then run this again.
        pause
        exit /b 1
    )
) else (
    echo         Already installed
)

REM --- Data folders ----------------------------------------------------------
echo   [4/5] Checking data folders...
for %%d in (
    "input\marketing_copy"
    "input\policy_documents"
    "scraping_info"
    "regulatory_updates"
    "alerts"
    "output"
) do (
    if not exist "%%~d" mkdir "%%~d" 2>nul
)
echo         Ready

REM --- API key ---------------------------------------------------------------
echo   [5/5] Checking API key...

if not exist ".env" (
    echo.
    echo   No .env file found. The agent needs an Anthropic API key.
    echo   Get one at https://console.anthropic.com  (API Keys - Create Key)
    echo.
    set /p APIKEY="   Paste your key (starts with sk-ant-) then press Enter: "
    if "!APIKEY!"=="" (
        echo.
        echo   [X] No key entered. Create a .env file containing:
        echo       ANTHROPIC_API_KEY=sk-ant-your-key
        pause
        exit /b 1
    )
    > .env echo ANTHROPIC_API_KEY=!APIKEY!
    echo.
    echo         Saved to .env
    echo         This file holds a secret - keep it out of git.
) else (
    echo         Found .env
)

REM --- Warn if the parse patch has not been applied ---------------------------
if exist "json_extract.py" goto :patched
findstr /c:"```(?:json)?" compliance_engine.py >nul 2>&1
if !errorlevel! equ 0 (
    echo.
    echo   ------------------------------------------------------------------
    echo   NOTE: compliance_engine.py still uses the fenced-only JSON regex.
    echo   Findings from the A1-J checklist will not reach your reports.
    echo   See complyline\patches\INTEGRATION.md for the two-line fix.
    echo   ------------------------------------------------------------------
)
:patched

REM --- Launch ----------------------------------------------------------------
echo.
echo   Starting. The app opens at http://localhost:8501
echo   Close this window or press Ctrl+C to stop.
echo.

%VPY% -m streamlit run app.py

pause
