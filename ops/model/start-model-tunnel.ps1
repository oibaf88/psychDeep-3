param(
    [Parameter(Mandatory = $true)]
    [string]$TunnelName,
    [string]$LocalModelBaseUrl = "http://127.0.0.1:1234/v1"
)

$ErrorActionPreference = "Stop"

Write-Host "PsychDeep vNext — model tunnel only"
Write-Host "Checking local OpenAI-compatible server: $LocalModelBaseUrl/models"

try {
    $models = Invoke-RestMethod -Method Get -Uri "$($LocalModelBaseUrl.TrimEnd('/'))/models" -TimeoutSec 5
    Write-Host "Local model server reachable."
} catch {
    throw "The local model server is not reachable. Start LM Studio/Ollama first. No database/API/frontend is started by this script."
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    throw "cloudflared is not installed or not on PATH."
}

Write-Host "Starting named tunnel '$TunnelName'."
Write-Host "The tunnel configuration must expose ONLY the model server over authenticated HTTPS."
Write-Host "Never expose PostgreSQL, the PsychDeep API, Docker, or a LAN administration port."

& cloudflared tunnel run $TunnelName
