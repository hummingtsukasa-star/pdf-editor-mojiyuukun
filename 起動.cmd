@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.10 or later is required. Install Python and try again.
    pause
    exit /b 1
  )
  python -m venv .venv
  if errorlevel 1 goto failed
  .venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto failed
)
start "PDF Mojiyuukun" ".venv\Scripts\pythonw.exe" "src\mojiyuu.py"
exit /b 0
:failed
echo Setup failed. Check the Python installation and internet connection.
pause
exit /b 1
