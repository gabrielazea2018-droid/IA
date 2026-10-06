# Detiene y opcionalmente elimina TODO el stack:
#   frontend (React) + backend (FastAPI) + pgAdmin + PostGIS
#
# Uso:   .\detener.ps1              -> docker compose down  (conserva los datos)
#        .\detener.ps1 -Purgar      -> docker compose down -v (borra la BD y pgAdmin)
#        .\detener.ps1 -SoloServicios -> baja compose pero deja la BD corriendo

[CmdletBinding()]
param(
    [switch]$Purgar,
    [switch]$SoloServicios
)

$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- Localizar Docker CLI ---
$dockerDir = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
if (Test-Path $dockerDir) { $env:PATH = "$dockerDir;$env:PATH" }
$docker = Get-Command docker -ErrorAction SilentlyContinue

Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ' Visor geografico de Bogota - deteniendo stack' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan

# 1) Procesos locales de respaldo (si se arranco el backend/frontend fuera de Docker)
Write-Host "`n[1/3] Cerrando procesos locales (uvicorn/vite) ..." -ForegroundColor Cyan
$cerrados = 0
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'uvicorn\s+backend\.main:app|\\vite(\.js)?\b|npm\.cmd run dev' } |
    ForEach-Object {
        Write-Host ("   deteniendo PID {0}" -f $_.ProcessId) -ForegroundColor DarkGray
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $script:cerrados++
    }
if ($cerrados -eq 0) { Write-Host '   ninguno corriendo' -ForegroundColor DarkGray }

# 2) Docker Compose
if ($docker) {
    Write-Host "`n[2/3] docker compose down ..." -ForegroundColor Cyan
    if ($Purgar) {
        Write-Warning '   -Purgar: se ELIMINARAN los volumenes (base de datos y pgAdmin).'
        & $docker compose -f (Join-Path $raiz 'docker-compose.yml') down -v --remove-orphans
    }
    elseif ($SoloServicios) {
        & $docker compose -f (Join-Path $raiz 'docker-compose.yml') stop backend frontend
        & $docker compose -f (Join-Path $raiz 'docker-compose.yml') rm -f backend frontend
    }
    else {
        & $docker compose -f (Join-Path $raiz 'docker-compose.yml') down --remove-orphans
    }
    Write-Host ('   exit code: {0}' -f $LASTEXITCODE) -ForegroundColor DarkGray
}
else {
    Write-Warning 'No se encontro el CLI de Docker; se omitio docker compose down.'
}

# 3) Estado final
Write-Host "`n[3/3] Estado de contenedores:" -ForegroundColor Cyan
if ($docker) { & $docker ps -a --filter 'name=bogota_pois' --format '{{.Names}} | {{.Status}}' }

Write-Host ''
if ($Purgar) {
    Write-Host 'Todo detenido y volumenes borrados. Para re-crear desde cero: .\iniciar.ps1' -ForegroundColor Yellow
}
else {
    Write-Host 'Stack detenido (los datos se conservan). Para volver a levantarlo: .\iniciar.ps1' -ForegroundColor Green
}
