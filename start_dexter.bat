@echo off
cd /d "%~dp0"
echo ============================================
echo   Dexter is starting...
echo ============================================
echo.

:: --- 1. Check Python venv ---
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Please create a virtual environment first:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt -r desktop\requirements.txt
    pause
    exit /b 1
)

:: --- 2. Install/update dependencies (quick, silent) ---
echo [1/4] Checking dependencies...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt -r desktop\requirements.txt 2>nul

:: --- 3. Create data directories ---
echo [2/4] Preparing data directories...
if not exist "data" mkdir data

:: --- 4. Start backend server ---
echo [3/4] Starting Dexter backend...
start /b .venv\Scripts\pythonw.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1

:: Wait a moment for the server to initialize
echo [4/5] Waiting for the backend to start...
timeout /t 5 /nobreak >nul

echo [5/5] Verifying backend health...
powershell -NoProfile -Command "try { Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 5 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
    echo WARNING: Backend did not respond at http://127.0.0.1:8000
    echo   Check backend.log and desktop_error.log for details.
) else (
    echo Backend appears to be running.
)

:: --- 6. Launch desktop app ---
echo Starting Dexter desktop...
start /b .venv\Scripts\pythonw.exe -m desktop.main > desktop_error.log 2>&1

echo.
echo Dexter is ready! Check your system tray.
echo   - Double-click the orange icon to open the Dashboard
echo   - Right-click for quick actions (Listen Now, Wake Word, etc.)
echo.
echo If the tray says backend offline, check backend.log and desktop_error.log for details.
