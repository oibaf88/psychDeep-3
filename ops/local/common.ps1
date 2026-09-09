# Shared operator preflight. Keep resolved configuration in memory: it contains
# secrets and must never be printed or included in an exception.
function Get-PsychDeepComposeConfig {
    if (-not (Test-Path -LiteralPath '.env.local')) {
        throw 'Missing .env.local. Copy .env.local.example and set the local secrets first.'
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker was not found. Install Docker Desktop and its Compose plugin first.'
    }
    $resolved = & docker compose --env-file .env.local -f docker-compose.offline.yml config --format json 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose could not validate the local configuration. Check .env.local and docker-compose.offline.yml without sharing resolved secret values.'
    }
    try {
        $config = ($resolved -join "`n") | ConvertFrom-Json
    } catch {
        throw 'Docker Compose did not return valid configuration JSON.'
    }
    return $config
}

function Assert-PsychDeepLocalSecrets {
    param([Parameter(Mandatory)]$Config)
    $password = [string]$Config.services.db.environment.POSTGRES_PASSWORD
    $jwt = [string]$Config.services.backend.environment.JWT_SECRET
    if ([string]::IsNullOrWhiteSpace($password) -or $password -match '^CHANGE_ME' -or $password -eq 'psychapp') {
        throw 'Set a unique LOCAL_DB_PASSWORD in .env.local before starting the local stack.'
    }
    if ([string]::IsNullOrWhiteSpace($jwt) -or $jwt -match '^CHANGE_ME' -or $jwt.Length -lt 32) {
        throw 'Set JWT_SECRET to a random value of at least 32 characters in .env.local.'
    }
}

function Assert-PsychDeepDockerEngine {
    & docker info --format '{{.ServerVersion}}' *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Engine is unavailable. Start Docker Desktop and check this PowerShell session can access the engine.'
    }
}

function Write-PsychDeepUtf8File {
    param([string]$Path, [AllowEmptyString()][string]$Value)
    # Windows PowerShell 5.1 defaults to the system code page. Docker env files
    # and Linux-mounted token files need predictable UTF-8 without a BOM.
    [System.IO.File]::WriteAllText($Path, $Value, [System.Text.UTF8Encoding]::new($false))
}

function ConvertTo-PsychDeepJavaProperty {
    param([AllowEmptyString()][string]$Value)
    $encoded = [System.Text.StringBuilder]::new()
    foreach ($character in $Value.ToCharArray()) {
        $number = [int]$character
        if ($number -lt 33 -or $number -gt 126) {
            [void]$encoded.Append(('\u{0:x4}' -f $number))
        } elseif ('\=:#!'.Contains([string]$character)) {
            [void]$encoded.Append('\').Append($character)
        } else {
            [void]$encoded.Append($character)
        }
    }
    return $encoded.ToString()
}
