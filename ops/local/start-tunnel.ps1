$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..'))
. (Join-Path $PSScriptRoot 'common.ps1')

$config = Get-PsychDeepComposeConfig
Assert-PsychDeepLocalSecrets -Config $config
Assert-PsychDeepDockerEngine

$secretDir = 'ops/local/secrets'
$tokenFile = Join-Path $secretDir 'cloudflare-tunnel-token.txt'
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null

if (-not (Test-Path $tokenFile)) {
    Write-Host 'Cloudflare Tunnel token not found.' -ForegroundColor Yellow
    $secure = Read-Host 'Paste the tunnel token (the eyJ... value)' -AsSecureString
    $token = [System.Net.NetworkCredential]::new('', $secure).Password
    if ([string]::IsNullOrWhiteSpace($token)) { throw 'No token supplied.' }
    Write-PsychDeepUtf8File -Path $tokenFile -Value $token.Trim()
}

# A truncated token can still be valid base64 JSON but lack its tunnel secret,
# leaving the connector in an endless restart loop. Never print decoded fields.
$storedToken = (Get-Content -LiteralPath $tokenFile -Raw).Trim()
try {
    $tokenData = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($storedToken)) | ConvertFrom-Json
    $tunnelId = [Guid]::Empty
    $validToken = -not [string]::IsNullOrWhiteSpace([string]$tokenData.a) -and
        -not [string]::IsNullOrWhiteSpace([string]$tokenData.s) -and
        [Guid]::TryParse([string]$tokenData.t, [ref]$tunnelId)
} catch { $validToken = $false }
if (-not $validToken) {
    throw 'The Cloudflare Tunnel token is incomplete or invalid. Replace the token file with the complete token from the named tunnel connector instructions.'
}

Write-Host 'Starting outbound-only Cloudflare Tunnel...' -ForegroundColor Cyan
docker compose --env-file .env.local -f docker-compose.offline.yml --profile tunnel up -d cloudflared
if ($LASTEXITCODE -ne 0) { throw 'cloudflared failed to start.' }

Write-Host 'Tunnel container started.' -ForegroundColor Green
Write-Host 'Verify connector health and the protected /v1/models route before using it from Render.'
Write-Host 'In Cloudflare, publish the tunnel hostname to: http://host.docker.internal:1234'
Write-Host 'In LM Studio 0.4+, enable API-token authentication and use that token as the API key in PsychDeep.'
Write-Host 'Never route PostgreSQL (5432/5433) through this tunnel.' -ForegroundColor Yellow
