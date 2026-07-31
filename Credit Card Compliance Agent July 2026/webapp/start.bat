@echo off
echo.
echo  ComplyLine - Starting local server...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install from python.org
    pause
    exit /b 1
)

REM Run the server
python server.py %*

pause
