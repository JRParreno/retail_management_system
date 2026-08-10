@echo off
REM Resolve a real Python 3 and run: _python.cmd <script> [args...]
REM Skips the Microsoft Store stub under WindowsApps.

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 --version >nul 2>&1
  if not errorlevel 1 (
    py -3 %*
    exit /b %ERRORLEVEL%
  )
)

if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%ProgramFiles%\Python313\python.exe" (
  "%ProgramFiles%\Python313\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%ProgramFiles%\Python312\python.exe" (
  "%ProgramFiles%\Python312\python.exe" %*
  exit /b %ERRORLEVEL%
)
if exist "%ProgramFiles%\Python311\python.exe" (
  "%ProgramFiles%\Python311\python.exe" %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not installed ^(or not on PATH — Microsoft Store stub only^).
echo Install: winget install --id Python.Python.3.12 -e --source winget
echo   or https://www.python.org/downloads/  ^(check "Add python.exe to PATH"^)
echo Then open a NEW terminal. Disable App execution aliases for python.exe if needed.
exit /b 1
