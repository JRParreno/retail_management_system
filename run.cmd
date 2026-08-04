@echo off
REM Windows launcher for MotoShop RMS menu
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 scripts\dev_menu.py %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\dev_menu.py %*
  exit /b %ERRORLEVEL%
)
echo Python 3 not found. Install Python 3 and try again.
exit /b 1
