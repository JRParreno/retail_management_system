@echo off
REM Hard-delete ALL products (interactive yes/no).
cd /d "%~dp0\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0delete_all_products.ps1" %*
exit /b %ERRORLEVEL%
