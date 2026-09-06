$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$pidFile = Join-Path $PSScriptRoot ".run\django-server.pid"
$urlFile = Join-Path $PSScriptRoot ".run\django-server.url"
$port = 8000
if ($env:ALUMNI_TRACKER_PORT) {
    $configuredPort = 0
    if ([int]::TryParse($env:ALUMNI_TRACKER_PORT, [ref] $configuredPort) -and
        $configuredPort -ge 1 -and $configuredPort -le 65535) {
        $port = $configuredPort
    }
}
elseif (Test-Path -LiteralPath $urlFile) {
    try {
        $port = ([Uri](Get-Content -LiteralPath $urlFile -Raw).Trim()).Port
    }
    catch {
        $port = 8000
    }
}

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

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Host "Alumni Tracker is not running (no PID file found)."
    exit 0
}

$savedPidText = (Get-Content -LiteralPath $pidFile -Raw).Trim()
$savedPid = 0
if (-not [int]::TryParse($savedPidText, [ref] $savedPid)) {
    Remove-Item -LiteralPath $pidFile -Force
    Remove-Item -LiteralPath $urlFile -Force -ErrorAction SilentlyContinue
    throw "The PID file was invalid and has been removed."
}

$server = Get-ServerProcess $savedPid
if (-not $server) {
    Remove-Item -LiteralPath $pidFile -Force
    Remove-Item -LiteralPath $urlFile -Force -ErrorAction SilentlyContinue
    Write-Host "Alumni Tracker is already stopped. Removed a stale PID file."
    exit 0
}

Write-Host "Stopping Alumni Tracker (PID $savedPid)..."
& taskkill.exe /PID $savedPid /T /F 2>$null | Out-Null

$stopped = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (-not (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) -and
        -not (Test-TcpPort "127.0.0.1" $port)) {
        $stopped = $true
        break
    }
}

if (-not $stopped) {
    throw "The server process tree did not stop cleanly."
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $urlFile -Force -ErrorAction SilentlyContinue
Write-Host "Alumni Tracker stopped."
