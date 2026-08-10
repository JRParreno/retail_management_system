@echo off
REM Windows CMD launcher for MotoShop RMS local / dev menu
REM Usage: scripts\local_run.bat   or   scripts\local_run.bat 5
cd /d "%~dp0.."
call "%~dp0_python.cmd" scripts\dev_menu.py %*
exit /b %ERRORLEVEL%
