@echo off
title AI Desktop Assistant

echo ========================================
echo   AI Desktop Assistant - Starting...
echo ========================================
echo.

cd /d "%~dp0"

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.8+ and add to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check deps, auto install on first run
python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] First run, installing dependencies...
    echo.
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Install failed. Please run manually: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo [OK] Dependencies installed!
    echo.
)

:: Start
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [EXIT] Error code: %errorlevel%
    pause
)
