param(
    [switch]$Check,
    [ValidateRange(15, 1800)]
    [int]$WaitTimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
. (Join-Path $PSScriptRoot 'common.ps1')

if (-not (Test-Path '.env.local')) {
    if ($Check) { throw 'Missing .env.local. Copy .env.local.example and set the local secrets first.' }
    Copy-Item '.env.local.example' '.env.local'
    Write-Host 'Created .env.local from template.' -ForegroundColor Yellow
    Write-Host 'Edit LOCAL_DB_PASSWORD and JWT_SECRET, then run this script again.' -ForegroundColor Yellow
    exit 1
}

$config = Get-PsychDeepComposeConfig
Assert-PsychDeepLocalSecrets -Config $config
if ($Check) {
    Write-Host 'Local Compose configuration and required secrets passed preflight. No services were started.' -ForegroundColor Green
    return
}
Assert-PsychDeepDockerEngine

Write-Host 'Starting PsychDeep local/offline...' -ForegroundColor Cyan
docker compose --env-file .env.local -f docker-compose.offline.yml up -d --build --wait --wait-timeout $WaitTimeoutSeconds db backend frontend
if ($LASTEXITCODE -ne 0) { throw 'Local services did not become healthy. Inspect docker compose ps and sanitized service logs; preserve the database volume.' }

Write-Host ''
Write-Host 'PsychDeep local is ready at: http://127.0.0.1:5173' -ForegroundColor Green
Write-Host 'API health:               http://127.0.0.1:8001/api/v1/health'
Write-Host 'PostgreSQL:               127.0.0.1:5433 (local machine only)'
Write-Host ''
Write-Host 'LM Studio (needed because PsychDeep backend runs inside Docker):' -ForegroundColor Cyan
Write-Host '  1. Developer > Server Settings > Require Authentication: ON'
Write-Host '  2. Create/copy an LM Studio API token.'
Write-Host '  3. Serve on Local Network: ON (or bind the server to 0.0.0.0).'
Write-Host '  4. Start the server on port 1234.'
Write-Host '  5. In PsychDeep Settings use:'
Write-Host '       URL:     http://host.docker.internal:1234/v1'
Write-Host '       API key: the LM Studio token'
Write-Host ''
Write-Host 'Keep Windows Firewall on; do not expose port 1234 to public networks.' -ForegroundColor Yellow
