@echo off
TITLE Instalador — AND Live Translator (vMix Broadcast)
echo =========================================================================
echo   INSTALADOR AUTOMATICO: AND LIVE TRANSLATOR (vMix Edition)
echo =========================================================================
echo.
cd /d "%~dp0"

where uv >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] Detectado gestor de paquetes UV. Configurando entorno ultra-rapido...
    uv venv .venv --python 3.11
    uv pip install -r requirements.txt --python .venv\Scripts\python.exe
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] No se ha encontrado Python ni UV en el sistema.
        echo Por favor instala Python 3.10 o superior marcando 'Add Python to PATH'.
        pause
        exit /b 1
    )
    echo [*] Creando entorno virtual Python...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo [*] Instalando dependencias de audio y red...
    python -m pip install --upgrade pip
    pip install -r requirements.txt
)

if not exist .env (
    if exist .env.example (
        echo [*] Creando archivo de configuracion inicial .env...
        copy .env.example .env >nul
    )
)

echo.
echo =========================================================================
echo   INSTALACION COMPLETADA CON EXITO
echo =========================================================================
echo   Para arrancar el motor ejecuta: start.bat
echo   Recuerda configurar tu GROQ_API_KEY en el archivo .env
echo =========================================================================
echo.
pause
