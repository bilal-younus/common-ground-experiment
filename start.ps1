$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Install and start Docker Desktop: https://docs.docker.com/get-docker/'
    Write-Host 'Node.js, npm, Python and PostgreSQL are not needed on your computer.'
    exit 1
}
docker compose version | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'Docker Compose v2 is required.'; exit 1 }
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host 'Start Docker Desktop, then try again.'; exit 1 }
Write-Host 'Building the application and starting PostgreSQL. The first run downloads dependencies.'
docker compose up --build -d --wait
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host 'Ready: http://localhost:8000'
Write-Host 'Stop with: docker compose down'
