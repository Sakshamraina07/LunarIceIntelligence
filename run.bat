@echo off
title Lunar Ice Intelligence Launcher
echo ==============================================================================
echo       LUNAR ICE INTELLIGENCE ^& MISSION CONTROL SYSTEM v2.0
echo       Chandrayaan-2 Radar Analysis ^& Science-Aware Rover Planning
echo ==============================================================================
echo.
echo 1. Starting FastAPI Scientific Backend (Port 8000)...
start "Lunar Ice Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

ping -n 3 127.0.0.1 >nul

echo 2. Starting GIS Interactive Mission Control (Port 5173)...
start "GIS Mission Control" cmd /k "cd /d %~dp0frontend && npm run dev"

ping -n 3 127.0.0.1 >nul

echo.
echo ==============================================================================
echo Systems online!
echo   GIS Mission Control: http://localhost:5173/
echo   API Docs:            http://127.0.0.1:8000/docs
echo ==============================================================================
start http://localhost:5173/
