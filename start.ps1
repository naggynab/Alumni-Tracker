$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

# This launcher is for local development. Override inherited environment values
# such as DEBUG=release so Django does not redirect the HTTP development server
# to HTTPS, which the local server does not provide.
$env:DEBUG = "True"

$pythonCandidates = @()
if ($env:ALUMNI_TRACKER_PYTHON) {
    $pythonCandidates += $env:ALUMNI_TRACKER_PYTHON
}
$pythonCandidates += Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$pythonCandidates += Join-Path $PSScriptRoot ".venv313\Scripts\python.exe"

$python = $null
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path -LiteralPath $candidate)) {
        continue
    }

    try {
        $versionText = (& $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
        $versionParts = $versionText.Split('.')
        $major = [int]$versionParts[0]
        $minor = [int]$versionParts[1]
        # Django 4.2.14 in requirements.txt is supported through Python 3.13.
        if ($major -eq 3 -and $minor -le 13) {
            $python = $candidate
            break
        }
    }
    catch {
        continue
    }
}

$runDirectory = Join-Path $PSScriptRoot ".run"
$logDirectory = Join-Path $PSScriptRoot "logs"
$pidFile = Join-Path $runDirectory "django-server.pid"
$urlFile = Join-Path $runDirectory "django-server.url"
$hostAddress = if ($env:ALUMNI_TRACKER_HOST) { $env:ALUMNI_TRACKER_HOST } else { "127.0.0.1" }
$port = 8000
if ($env:ALUMNI_TRACKER_PORT) {
    $configuredPort = 0
    if (-not [int]::TryParse($env:ALUMNI_TRACKER_PORT, [ref] $configuredPort) -or
        $configuredPort -lt 1 -or $configuredPort -gt 65535) {
        throw "ALUMNI_TRACKER_PORT must be a valid TCP port number."
    }
    $port = $configuredPort
}

if (-not $python) {
    throw "No compatible project Python was found. Use Python 3.12 or 3.13 and install requirements.txt in .venv."
}

New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

function Get-ServerProcess([int] $processId) {
    try {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction Stop
        if ($process -and ([string] $process.CommandLine -match "manage\.py.*runserver")) {
            return $process
        }
    }
    catch {
        return $null
    }

    return $null
}

function Test-TcpPort([string] $address, [int] $targetPort) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.BeginConnect($address, $targetPort, $null, $null)
        if ($connection.AsyncWaitHandle.WaitOne(250) -and $client.Connected) {
            return $true
        }
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }

    return $false
}

function Stop-ServerTree([int] $processId) {
    & taskkill.exe /PID $processId /T /F 2>$null | Out-Null
}

if (Test-Path -LiteralPath $pidFile) {
    $savedPidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
    $savedPid = 0
    if ([int]::TryParse($savedPidText, [ref] $savedPid)) {
        if (Get-ServerProcess $savedPid) {
            if (Test-Path -LiteralPath $urlFile) {
                try {
                    $runningUri = [Uri](Get-Content -LiteralPath $urlFile -Raw).Trim()
                    $hostAddress = $runningUri.Host
                    $port = $runningUri.Port
                }
                catch {
                    # Fall back to the configured host and port when the URL file is stale.
                }
            }
            Write-Host "Alumni Tracker is already running (PID $savedPid)."
            Write-Host "Open http://$hostAddress`:$port/"
            "http://$hostAddress`:$port/" | Set-Content -LiteralPath $urlFile -Encoding ASCII
            exit 0
        }
    }

    Remove-Item -LiteralPath $pidFile -Force
}

if (Test-TcpPort $hostAddress $port) {
    if ($env:ALUMNI_TRACKER_PORT) {
        throw "Port $port is already in use. Stop the process using it or choose another port."
    }

    $firstBusyPort = $port
    do {
        $port++
    } while ($port -le 65535 -and (Test-TcpPort $hostAddress $port))

    if ($port -gt 65535) {
        throw "No free TCP port was found for the local server."
    }
    Write-Host "Port $firstBusyPort is already in use; using port $port instead."
}

Write-Host "Applying database migrations..."
& $python manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) {
    throw "Database migrations failed. The server was not started."
}

$stdoutLog = Join-Path $logDirectory "django-server.log"
$stderrLog = Join-Path $logDirectory "django-server-error.log"

Write-Host "Starting Alumni Tracker on http://$hostAddress`:$port/ ..."
$server = Start-Process `
    -FilePath $python `
    -ArgumentList @("manage.py", "runserver", "$hostAddress`:$port", "--noreload") `
    -WorkingDirectory $PSScriptRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

$server.Id | Set-Content -LiteralPath $pidFile -Encoding ASCII

$ready = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250

    if ($server.HasExited) {
        break
    }

    if (Test-TcpPort $hostAddress $port) {
        $ready = $true
        break
    }
}

if (-not $ready) {
    if (-not $server.HasExited) {
        Stop-ServerTree $server.Id
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $urlFile -Force -ErrorAction SilentlyContinue
    throw "The server did not begin listening on port $port. Check logs\django-server-error.log for details."
}

"http://$hostAddress`:$port/" | Set-Content -LiteralPath $urlFile -Encoding ASCII
Write-Host "Alumni Tracker started (PID $($server.Id))."
Write-Host "Python: $python"
Write-Host "Open http://$hostAddress`:$port/"
Write-Host "Run .\stop.ps1 to stop it."
