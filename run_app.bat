@echo off
echo Starting Momentum Screener...
cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo Virtual environment not found. Please run the installation steps first.
    pause
    exit /b
)

echo Using Python from: %~dp0venv\Scripts\python.exe
"%~dp0venv\Scripts\python.exe" backend/main.py
pause
