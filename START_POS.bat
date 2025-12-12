@echo off
REM Cid-POS System - Windows Launcher
REM Double-click this file to start the POS system

title Cid-POS System Launcher

echo.
echo ========================================
echo   Cid-POS System - Starting...
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.8+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM Run the setup and launch script
python run_windows.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Setup or launch failed. Please check the errors above.
    pause
)
