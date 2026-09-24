@echo off
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
  set "PY=venv\Scripts\python.exe"
) else if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  echo No venv found. From this folder run:
  echo   py -3.12 -m venv venv
  echo   venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

REM Must be set before Python starts so PortAudio/sounddevice can enumerate ASIO.
set "SD_ENABLE_ASIO=1"

echo Starting Lights on http://127.0.0.1:8800 (SD_ENABLE_ASIO=%SD_ENABLE_ASIO%)
"%PY%" backend\main.py
