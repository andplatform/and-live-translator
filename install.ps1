# Instalador y Verificador PowerShell para AND Live Translator
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  DESPLIEGUE Y VERIFICACION: AND LIVE TRANSLATOR (vMix Edition)" -ForegroundColor Cyan
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host ""

 = Split-Path -Parent System.Management.Automation.InvocationInfo.MyCommand.Path

# 1. Comprobar gestor de paquetes
if (Get-Command "uv" -ErrorAction SilentlyContinue) {
    Write-Host "[+] Gestor UV detectado. Creando .venv con Python 3.11..." -ForegroundColor Green
    & uv venv "\.venv" --python 3.11
    & uv pip install -r "\requirements.txt" --python "\.venv\Scripts\python.exe"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    Write-Host "[+] Python detectado. Creando .venv..." -ForegroundColor Green
    & python -m venv "\.venv"
    & "\.venv\Scripts\pip.exe" install --upgrade pip
    & "\.venv\Scripts\pip.exe" install -r "\requirements.txt"
} else {
    Write-Host "[-] ERROR: Se requiere Python 3.10+ o UV para continuar." -ForegroundColor Red
    Exit 1
}

# 2. Configuración inicial de .env
if (-not (Test-Path "\.env")) {
    if (Test-Path "\.env.example") {
        Copy-Item "\.env.example" "\.env"
        Write-Host "[+] Archivo .env generado desde plantilla." -ForegroundColor Green
    }
}

# 3. Enumeración de dispositivos de audio
Write-Host ""
Write-Host "[*] Diagnosticando tarjetas de audio y cables virtuales..." -ForegroundColor Yellow
& "\.venv\Scripts\python.exe" -c "import sounddevice as sd; devs = sd.query_devices(); print(f'Dispositivos encontrados: {len(devs)}'); [print(f'  - [{i}] {d[\"name\"]} (In:{d[\"max_input_channels\"]}, Out:{d[\"max_output_channels\"]})') for i, d in enumerate(devs) if d[\"max_input_channels\"] > 0 or d[\"max_output_channels\"] > 0]"

Write-Host ""
Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host "  INSTALACION VERIFICADA Y LISTA PARA TRANSMISION" -ForegroundColor Green
Write-Host "  Ejecuta start.bat para arrancar el servicio en el puerto 17494" -ForegroundColor White
Write-Host "=========================================================================" -ForegroundColor Cyan
