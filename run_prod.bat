@echo off
REM Windows CMD production deploy for MotoShop RMS
REM Usage: run_prod.bat   or   run_prod.bat --skip-build --with-tunnel quick
cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python scripts\prod_deploy.py %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 scripts\prod_deploy.py %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not found. Install from https://www.python.org/downloads/
exit /b 1
