# Run after copying the tunnel token or full Docker command from Cloudflare > Tunnels > Add a replica.
# Never supply the token as a command-line argument, and never commit secrets/.
param([switch]$Replace)

$ErrorActionPreference = 'Stop'
$clipboard = Get-Clipboard -Raw
if ([string]::IsNullOrWhiteSpace($clipboard)) {
    throw 'Clipboard empty. Copy the connector token or Docker installation command from Cloudflare first.'
}

# Cloudflare connector tokens are long base64 JSON strings beginning with eyJ.
$match = [regex]::Match($clipboard, '(?<![A-Za-z0-9+/_=-])(?<token>eyJ[A-Za-z0-9+/_=-]{80,})(?![A-Za-z0-9+/_=-])')
if (-not $match.Success) {
    throw 'No valid-looking tunnel token was found. In Cloudflare > Networking > Tunnels > select tunnel > Add a replica > Docker, copy the command. Do NOT paste a tunnel name, UUID, Access client secret or truncated token.'
}
$token = $match.Groups['token'].Value
try {
    $decoded = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($token))
    $null = $decoded | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw 'The clipboard value is not a complete base64-encoded Cloudflare tunnel token. Copy the entire Docker command again.'
}

$secretsDir = Join-Path $PSScriptRoot 'secrets'
$secretPath = Join-Path $secretsDir 'tunnel-token.txt'
if ((Test-Path -LiteralPath $secretPath) -and -not $Replace) {
    throw 'A local tunnel token already exists. To intentionally replace it, use .\save-token-from-clipboard.ps1 -Replace.'
}
New-Item -ItemType Directory -Path $secretsDir -Force | Out-Null
[IO.File]::WriteAllText($secretPath, $token, [Text.UTF8Encoding]::new($false))
Write-Host 'Tunnel token validated and stored in the local ignored secrets directory (value not displayed).'
Write-Host 'Do not copy this file into GitHub or paste its contents into PsychDeep or Render.'
