@echo off
REM Windows CMD production deploy / restart
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 scripts\prod_deploy.py %*
  exit /b %ERRORLEVEL%
)

where python3 >nul 2>nul
if %ERRORLEVEL%==0 (
  python3 scripts\prod_deploy.py %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python scripts\prod_deploy.py %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not found. Install Python 3 (python3 / py / python) and try again.
exit /b 1
