@echo off
chcp 65001 >nul
title AI Music Agent - Stop

echo ============================================================
echo   AI Music Agent - Stopping Services
echo ============================================================
echo.

:: Kill backend (python process running api.run)
echo [1/2] Stopping backend...
for /f "tokens=2" %%a in ('netstat -ano ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

:: Kill frontend (node/vite process on port 5173)
echo [2/2] Stopping frontend...
for /f "tokens=2" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo All services stopped.
echo.
