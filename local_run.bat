@echo off
REM Windows CMD launcher for MotoShop RMS local / dev menu
REM Usage: local_run.bat   or   local_run.bat 5
cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python scripts\dev_menu.py %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 scripts\dev_menu.py %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not found. Install from https://www.python.org/downloads/
echo   ^(check "Add python.exe to PATH"^) or: winget install Python.Python.3.12
exit /b 1
