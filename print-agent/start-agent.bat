@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create venv. Install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
  )
  echo Installing dependencies...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt -q
  if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
  )
)

if not exist ".env" (
  echo Missing .env — copy config.example.env to .env and set PRINT_AGENT_API_KEY.
  pause
  exit /b 1
)

echo Starting Azmus Print Agent...
".venv\Scripts\python.exe" agent.py
pause
