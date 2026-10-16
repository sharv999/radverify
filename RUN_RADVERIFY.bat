@echo off
cd /d "%~dp0"
python app.py
if errorlevel 1 (
  echo.
  echo RadVerify did not start. Check that Python and the project requirements are installed.
  pause
)
