# Build and start the inference-only Cloudflare connector from this directory.
# Prerequisites: Docker Desktop Linux containers, running LM Studio on port 1234,
# valid secrets/tunnel-token.txt and Cloudflare hostname origin configured.
$ErrorActionPreference = 'Stop'
$compose = Join-Path $PSScriptRoot 'compose.yaml'
$secret = Join-Path $PSScriptRoot 'secrets/tunnel-token.txt'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker CLI not found. Install/start Docker Desktop for Windows first.'
}
$engine = (& docker info --format '{{.OSType}}' 2>$null)
if ($LASTEXITCODE -ne 0 -or $engine.Trim() -ne 'linux') {
    throw 'Docker Desktop must be running in Linux containers mode.'
}
if (-not (Test-Path -LiteralPath $secret -PathType Leaf)) {
    throw 'Tunnel token missing. Copy the Cloudflare Docker command, then run .\save-token-from-clipboard.ps1.'
}
if ((Get-Item -LiteralPath $secret).Length -lt 80) {
    throw 'Tunnel token file is unexpectedly short. Recopy it using .\save-token-from-clipboard.ps1 -Replace.'
}
if (-not (Test-NetConnection -ComputerName 127.0.0.1 -Port 1234 -InformationLevel Quiet -WarningAction SilentlyContinue)) {
    throw 'LM Studio is not listening on Windows port 1234. Start its Developer API server first.'
}

& docker compose -f $compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Invalid Docker Compose configuration.' }
& docker compose -f $compose up --detach --build
if ($LASTEXITCODE -ne 0) { throw 'Docker build or container startup failed.' }
& docker compose -f $compose ps
if ($LASTEXITCODE -ne 0) { throw 'Could not check container status.' }
Write-Host 'Connector startup requested. Confirm tunnel HEALTHY in Cloudflare and test the protected /v1/models route from the backend.'
Write-Host 'If the connector exits, inspect: docker compose -f ops/model/docker/compose.yaml logs --tail=50 cloudflared'
