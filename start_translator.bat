@echo off
TITLE AND Live Translator — vMix Edition (17494)
cd /d "%~dp0"
echo ============================================================
echo   AND LIVE TRANSLATOR (vMix Broadcast Edition)
echo   Puerto: 17494
echo   Overlay: http://127.0.0.1:17494/overlay
echo   Panel:   http://127.0.0.1:17494/
echo ============================================================
echo.
.venv\Scripts\python.exe main.py
pause
