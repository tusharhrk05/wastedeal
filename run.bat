@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
) else (
    set "PYTHON=py"
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON% -m venv .venv
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -c "import flask" >nul 2>nul
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" app.py
goto finished

:failed
echo.
echo Could not prepare WasteDeal. Install Python 3.10 or newer and try again.

:finished
echo.
pause
endlocal
