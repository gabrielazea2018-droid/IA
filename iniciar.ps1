# Levanta TODO el stack con un solo comando:
#   1) PostGIS (+ seed de sitios geocodificados de Bogota)  2) pgAdmin  3) API FastAPI  4) Visor React
#
# Uso:   .\iniciar.ps1
#        .\iniciar.ps1 -Rebuild     (reconstruye las imagenes del backend/frontend)
#        .\iniciar.ps1 -Reinicio    (borra volumenes: re-ejecuta init.sql desde cero)

[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$Reinicio,
    [switch]$SinFrontend,
    [switch]$SinBackend
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path

# --- Localizar el CLI de Docker (Docker Desktop no siempre lo pone en el PATH) ---
$dockerDir = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin'
if (Test-Path $dockerDir) { $env:PATH = "$dockerDir;$env:PATH" }
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    foreach ($candidato in @(
        (Join-Path $env:LOCALAPPDATA 'Docker\wsl\cli-plugins\docker.exe'),
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    )) {
        if (Test-Path $candidato) { $docker = $candidato; break }
    }
}
if (-not $docker) { Write-Error 'No se encontro el CLI de Docker. Abre Docker Desktop e intenta de nuevo.' }

if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
    Write-Host 'Arrancando Docker Desktop...' -ForegroundColor Yellow
    Start-Process 'Docker Desktop' -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 25
}

function Invoke-Docker { & $docker @args }

Write-Host '==============================================' -ForegroundColor Cyan
Write-Host ' Visor geografico de Bogota - iniciando stack' -ForegroundColor Cyan
Write-Host '==============================================' -ForegroundColor Cyan

$extras = @()
if ($Rebuild)  { $extras += '--build' }
if ($Reinicio) {
    # `up -v` solo recrea volumenes ANONIMOS; los nombrados (pgdata, pgadmin_data)
    # hay que borrarlos explicitamente para que init.sql vuelva a correr.
    Write-Host '   -Reinicio: eliminando volumenes (base de datos y pgAdmin) ...' -ForegroundColor Yellow
    Invoke-Docker compose -f (Join-Path $raiz 'docker-compose.yml') down -v --remove-orphans
    if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo docker compose down -v' }
    $extras += '--build'
}

$servicios = @('db', 'pgadmin')
if (-not $SinBackend)  { $servicios += 'backend' }
if (-not $SinFrontend) { $servicios += 'frontend' }

Write-Host "`n[1/3] Docker Compose: $($servicios -join ', ') ..." -ForegroundColor Cyan
Invoke-Docker compose -f (Join-Path $raiz 'docker-compose.yml') up -d @extras
if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo docker compose up' }

# --- Esperar a que la base este sana antes de continuar ---
Write-Host '[2/3] Esperando a que PostGIS este sano ...' -ForegroundColor Cyan
$deadline = (Get-Date).AddSeconds(120)
$ok = $false
while ((Get-Date) -lt $deadline) {
    $estado = Invoke-Docker inspect -f '{{.State.Health.Status}}' bogota_pois_db 2>$null
    if ($estado -eq 'healthy') { $ok = $true; break }
    Start-Sleep -Seconds 3
}
if (-not $ok) { Write-Warning 'La base no marco "healthy" en 120s; revisa: docker compose logs db' }

# --- Comprobar la API (local o contenedor) ---
Write-Host '[3/3] Comprobando servicios ...' -ForegroundColor Cyan
$apiUrl   = 'http://127.0.0.1:8000/api/salud'
$webUrl   = 'http://127.0.0.1:5173/'
$pgAdmin  = 'http://127.0.0.1:5050/'

function Test-Url($url, $intentos = 20) {
    for ($i = 1; $i -le $intentos; $i++) {
        try {
            $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -in 200, 302) { return $true }
        } catch { Start-Sleep -Seconds 2 }
    }
    return $false
}

$apiOk  = Test-Url $apiUrl
$webOk  = Test-Url $webUrl
$pgOk   = Test-Url $pgAdmin

Write-Host ''
Write-Host '----------------------------------------------' -ForegroundColor DarkGray

function Mostrar-Servicio($nombre, $url, $ok, $nota = '') {
    $marca = if ($ok) { '[ OK ]' } else { '[ -- ]' }
    $color = if ($ok) { 'Green' } else { 'Yellow' }
    Write-Host ("{0} {1,-9} {2}" -f $marca, $nombre, $url) -ForegroundColor $color
    if ($nota) { Write-Host ("        {0}" -f $nota) -ForegroundColor DarkGray }
}

Mostrar-Servicio 'Visor'   $webUrl  $webOk  'React + Leaflet (mapa de Bogota)'
Mostrar-Servicio 'API'     $apiUrl  $apiOk  'Swagger en http://127.0.0.1:8000/docs'
Mostrar-Servicio 'pgAdmin' $pgAdmin $pgOk   'admin@example.com / admin'
Mostrar-Servicio 'PostGIS' 'postgresql://bogota:bogota@localhost:5432/bogota' $ok 'seed geocodificado de sitios (ver db/seed.json)'

Write-Host '----------------------------------------------' -ForegroundColor DarkGray
Write-Host "Documentacion OpenAPI: http://127.0.0.1:8000/openapi.json" -ForegroundColor DarkGray
Write-Host "Detener todo:          .\detener.ps1`n" -ForegroundColor DarkGray

if (-not ($apiOk -and $webOk -and $pgOk)) {
    Write-Warning 'Algunos servicios no respondieron. Diagnosticos utiles:'
    Write-Host '   docker compose logs db backend pgadmin frontend'
}
