@echo off
chcp 65001 >nul
title AI Music Agent - Launcher

echo ============================================================
echo   AI Music Agent - One-Click Start
echo ============================================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python and add to PATH.
    pause
    exit /b 1
)

:: Check if node is available
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js and add to PATH.
    pause
    exit /b 1
)

:: Check if port 5000 is already in use
netstat -ano | findstr ":5000 " | findstr "LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port 5000 is already in use. Backend may already be running.
    echo        If you want to restart, run stop.bat first.
    pause
    exit /b 1
)

:: Start backend (use cmd /k so window stays open on error)
echo [1/2] Starting backend server (Flask on port 5000)...
start "AI-Music-Backend" cmd /k "cd /d %~dp0 && python -m api.run"

:: Wait a moment for backend to initialize
timeout /t 2 /nobreak >nul

:: Start frontend
echo [2/2] Starting frontend dev server (Vite on port 5173)...
start "AI-Music-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: Wait for frontend to be ready
timeout /t 3 /nobreak >nul

:: Open browser
echo.
echo Opening browser...
start http://localhost:5173

echo.
echo ============================================================
echo   Both servers are running in separate windows.
echo   Backend:  http://127.0.0.1:5000
echo   Frontend: http://localhost:5173
echo.
echo   To stop all services, run stop.bat
echo ============================================================
echo.
