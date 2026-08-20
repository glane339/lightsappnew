# Stop the Lights App operator server (default port 8800).
# Usage: .\stop-server.cmd
#        .\stop-server.ps1
#        .\stop-server.ps1 -Port 8800 -GracefulSeconds 8
#
# Tries POST /api/shutdown first so uvicorn lifespan can blackout and close the
# sACN socket (F-04). Force-kill is a timed fallback, and only for python
# processes whose command line contains THIS repo's backend\main.py.

param(
    [int]$Port = 8800,
    [int]$GracefulSeconds = 8
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainPy = (Join-Path $repoRoot "backend\main.py")
$mainNeedle = ($mainPy -replace "/", "\").ToLowerInvariant()

function Get-LightsAppProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -match '^(pythonw?|py)\.exe$' -and
            $_.CommandLine -and
            (($_.CommandLine -replace "/", "\").ToLowerInvariant().Contains($mainNeedle))
        }
}

function Stop-OurProcess {
    param([int]$ProcessId, [string]$Reason)
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        return
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Force-stopped PID $ProcessId ($Reason)"
}

$ours = @(Get-LightsAppProcesses)
if ($ours.Count -eq 0) {
    Write-Host "No Lights App process found (command line matching $mainPy)."
    exit 1
}

$shutdownOk = $false
foreach ($target in @("127.0.0.1", "[::1]")) {
    try {
        Invoke-WebRequest -Uri "http://${target}:${Port}/api/shutdown" -Method POST -UseBasicParsing -TimeoutSec 3 |
            Out-Null
        $shutdownOk = $true
        Write-Host "Requested graceful shutdown on port $Port."
        break
    } catch {
        # Server may already be stopping, or bound only on one stack.
    }
}

$deadline = (Get-Date).AddSeconds([Math]::Max(1, $GracefulSeconds))
while ((Get-Date) -lt $deadline) {
    $still = @(Get-LightsAppProcesses)
    if ($still.Count -eq 0) {
        Write-Host "Stopped gracefully."
        exit 0
    }
    Start-Sleep -Milliseconds 250
}

foreach ($proc in Get-LightsAppProcesses) {
    Stop-OurProcess -ProcessId $proc.ProcessId -Reason "timed out after graceful shutdown"
}

$left = @(Get-LightsAppProcesses)
if ($left.Count -eq 0) {
    if ($shutdownOk) {
        Write-Host "Done (forced after timeout)."
    } else {
        Write-Host "Done (forced; shutdown endpoint was unreachable)."
    }
    exit 0
}

Write-Host "Still running after force-kill: $($left.ProcessId -join ', ')"
exit 1
