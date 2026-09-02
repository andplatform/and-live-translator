@echo off
TITLE AND Live Translator — Master Broadcast Engine (17494)
cd /d "%~dp0"
cls
echo =========================================================================
echo   AND LIVE TRANSLATOR (vMix Broadcast Edition)
echo =========================================================================
echo   Panel de Control Operador:   http://127.0.0.1:17494/
echo   Rótulo Web Browser Overlay:  http://127.0.0.1:17494/overlay
echo =========================================================================
echo.

if not exist .venv\Scripts\python.exe (
    echo [!] No se encontro el entorno virtual. Ejecutando instalacion...
    call install.bat
)

.venv\Scripts\python.exe main.py
pause
