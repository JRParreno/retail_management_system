@echo off
REM Windows CMD DB backup helper
cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python scripts\db_backup.py %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 scripts\db_backup.py %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not found.
exit /b 1
