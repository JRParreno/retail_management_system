@echo off
REM Windows CMD production deploy for MotoShop RMS
REM Usage: scripts\run_prod.bat   or   scripts\run_prod.bat --skip-build
cd /d "%~dp0.."
call "%~dp0_python.cmd" scripts\prod_deploy.py %*
exit /b %ERRORLEVEL%
