# Stop the Lights App operator server (default port 8800).
# Usage: .\stop-server.cmd
#        .\stop-server.ps1   (requires execution policy that allows scripts)
#        .\stop-server.ps1 -Port 8800

param(
    [int]$Port = 8800
)

$ErrorActionPreference = "Stop"
$stopped = [System.Collections.Generic.HashSet[int]]::new()

function Stop-ServerProcess {
    param([int]$ProcessId, [string]$Reason)
    if ($stopped.Contains($ProcessId)) {
        return
    }
    $proc = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if (-not $proc) {
        return
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    [void]$stopped.Add($ProcessId)
    Write-Host "Stopped PID $ProcessId ($Reason)"
}

# Anything listening on the operator port (usually uvicorn).
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-ServerProcess -ProcessId $_.OwningProcess -Reason "port $Port" }

# Fallback: python started as backend/main.py even if the port query misses it.
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'backend[\\/]main\.py' } |
    ForEach-Object { Stop-ServerProcess -ProcessId $_.ProcessId -Reason "backend/main.py" }

if ($stopped.Count -eq 0) {
    Write-Host "No server found on port $Port."
    exit 1
}

Write-Host "Done. Stopped $($stopped.Count) process(es)."
exit 0
