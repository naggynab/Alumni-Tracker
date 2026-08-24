$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

# This launcher is for local development. Override inherited environment values
# such as DEBUG=release so Django does not redirect the HTTP development server
# to HTTPS, which the local server does not provide.
$env:DEBUG = "True"

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$runDirectory = Join-Path $PSScriptRoot ".run"
$logDirectory = Join-Path $PSScriptRoot "logs"
$pidFile = Join-Path $runDirectory "django-server.pid"
$hostAddress = "127.0.0.1"
$port = 8000

if (-not (Test-Path -LiteralPath $python)) {
    throw "The project virtual environment was not found at $python. Create it with: python -m venv .venv"
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
            Write-Host "Alumni Tracker is already running (PID $savedPid)."
            Write-Host "Open http://$hostAddress`:$port/"
            exit 0
        }
    }

    Remove-Item -LiteralPath $pidFile -Force
}

if (Test-TcpPort $hostAddress $port) {
    throw "Port $port is already in use. Stop the process using it or choose another port."
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
    throw "The server did not begin listening on port $port. Check logs\django-server-error.log for details."
}

Write-Host "Alumni Tracker started (PID $($server.Id))."
Write-Host "Open http://$hostAddress`:$port/"
Write-Host "Run .\stop.ps1 to stop it."
