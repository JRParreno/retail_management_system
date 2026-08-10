@echo off
REM Windows CMD DB backup helper
REM Usage: scripts\run_db_backup.bat status
cd /d "%~dp0.."
call "%~dp0_python.cmd" scripts\db_backup.py %*
exit /b %ERRORLEVEL%
