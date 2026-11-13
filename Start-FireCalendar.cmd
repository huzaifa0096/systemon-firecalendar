@echo off
setlocal
cd /d "%~dp0"
title FireCalendar local server
set "FIRECAL_PY=python"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import uvicorn, app.main" >nul 2>&1
  if not errorlevel 1 set "FIRECAL_PY=.venv\Scripts\python.exe"
)
echo Starting FireCalendar. Keep this window open while using the app.
"%FIRECAL_PY%" start_firecalendar.py
if errorlevel 1 pause
