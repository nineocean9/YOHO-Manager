@echo off
title MediScan AI
cd /d "%~dp0"
echo ========================================
echo  MediScan AI — Intelligent Medical Image Platform
echo ========================================
echo.
echo Starting application...
echo.
npx electron .
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start. Make sure Electron is installed.
    echo Run: npm install
    echo.
    pause
)