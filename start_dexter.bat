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
echo [1/3] Checking dependencies...
.venv\Scripts\python.exe -m pip install -q -r requirements.txt -r desktop\requirements.txt 2>nul

:: --- 3. Create data directories ---
echo [2/3] Preparing data directories...
if not exist "data" mkdir data

:: --- 4. Start backend server ---
echo [3/3] Starting Dexter backend...
start "Dexter Backend" /min .venv\Scripts\pythonw.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

:: Wait a moment for the server to initialize
timeout /t 3 /nobreak >nul

:: --- 5. Launch desktop app ---
echo.
echo Dexter is ready! Check your system tray.
echo   - Double-click the orange icon to open the Dashboard
echo   - Right-click for quick actions (Listen Now, Wake Word, etc.)
echo.
start "Dexter Desktop" /min .venv\Scripts\python.exe -m desktop.main 2> desktop_error.log
