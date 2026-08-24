$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$pidFile = Join-Path $PSScriptRoot ".run\django-server.pid"

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
    throw "The PID file was invalid and has been removed."
}

$server = Get-ServerProcess $savedPid
if (-not $server) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Host "Alumni Tracker is already stopped. Removed a stale PID file."
    exit 0
}

Write-Host "Stopping Alumni Tracker (PID $savedPid)..."
& taskkill.exe /PID $savedPid /T /F 2>$null | Out-Null

$stopped = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 500
    if (-not (Get-Process -Id $savedPid -ErrorAction SilentlyContinue) -and
        -not (Test-TcpPort "127.0.0.1" 8000)) {
        $stopped = $true
        break
    }
}

if (-not $stopped) {
    throw "The server process tree did not stop cleanly."
}

Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
Write-Host "Alumni Tracker stopped."
