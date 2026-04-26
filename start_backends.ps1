# PhishGuard - Backend Services Launcher (Windows)
# Starts PhishGuard + SecurBank + BreezeTech in background
#
# Usage:
#   .\start_backends.ps1          # Start all services
#   .\start_backends.ps1 -Stop    # Stop all services

param(
    [switch]$Stop
)

# Force UTF-8 console output
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$ROOT = $PSScriptRoot

# Service definitions
$services = @(
    @{
        Name    = "PhishGuard"
        Port    = 8000
        Cwd     = $ROOT
        Venv    = "$ROOT\venv\Scripts\python.exe"
        PidFile = "$ROOT\.pid_phishguard"
    },
    @{
        Name    = "SecurBank"
        Port    = 9000
        Cwd     = "$ROOT\mockups\bankingapp"
        Venv    = "$ROOT\mockups\bankingapp\venv\Scripts\python.exe"
        PidFile = "$ROOT\.pid_securbank"
    },
    @{
        Name    = "BreezeTech"
        Port    = 9001
        Cwd     = "$ROOT\mockups\startup"
        Venv    = "$ROOT\mockups\startup\venv\Scripts\python.exe"
        PidFile = "$ROOT\.pid_breezetech"
    }
)

function Write-Banner {
    Write-Host ""
    Write-Host "  ============================================================"
    Write-Host "    PhishGuard -- Backend Services Launcher"
    Write-Host "  ============================================================"
    Write-Host ""
}

# Stop all services
function Stop-AllServices {
    Write-Banner
    Write-Host "  Stopping all services..."
    Write-Host ""

    foreach ($svc in $services) {
        if (Test-Path $svc.PidFile) {
            $procId = Get-Content $svc.PidFile -ErrorAction SilentlyContinue
            if ($procId) {
                try {
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $procId } | ForEach-Object {
                        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                    }
                    Write-Host "  [OK] $($svc.Name) (PID $procId) stopped"
                } catch {
                    Write-Host "  [--] $($svc.Name) (PID $procId) was not running"
                }
            }
            Remove-Item $svc.PidFile -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "  [--] $($svc.Name) -- no PID file found"
        }
    }

    # Fallback: kill anything still on the ports
    foreach ($svc in $services) {
        $portListeners = Get-NetTCPConnection -LocalPort $svc.Port -ErrorAction SilentlyContinue
        foreach ($conn in $portListeners) {
            if ($conn.State -eq "Listen") {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "  [!!] Killed leftover process on port $($svc.Port)"
            }
        }
    }

    Write-Host ""
    Write-Host "  All services stopped."
    Write-Host ""
}

# Start all services
function Start-AllServices {
    Write-Banner

    # Check for existing processes and stop them first
    $anyRunning = $false
    foreach ($svc in $services) {
        $portListeners = Get-NetTCPConnection -LocalPort $svc.Port -ErrorAction SilentlyContinue
        foreach ($conn in $portListeners) {
            if ($conn.State -eq "Listen") {
                $anyRunning = $true
                break
            }
        }
    }
    if ($anyRunning) {
        Write-Host "  Existing services detected -- stopping them first..."
        Stop-AllServices
        Start-Sleep -Seconds 1
        Write-Banner
    }

    Write-Host "  Starting backend services..."
    Write-Host ""

    foreach ($svc in $services) {
        if (-not (Test-Path $svc.Venv)) {
            Write-Host "  [FAIL] $($svc.Name): venv not found at $($svc.Venv)"
            continue
        }

        $proc = Start-Process -FilePath $svc.Venv `
            -ArgumentList "-m", "backend.main" `
            -WorkingDirectory $svc.Cwd `
            -WindowStyle Hidden `
            -PassThru

        $proc.Id | Out-File -FilePath $svc.PidFile -NoNewline

        Write-Host "  [OK] $($svc.Name) started (PID $($proc.Id)) -> http://localhost:$($svc.Port)"
    }

    Write-Host ""
    Write-Host "  Waiting for services to initialize..."
    Start-Sleep -Seconds 3

    # Health checks
    Write-Host ""
    Write-Host "  Health Checks:"
    foreach ($svc in $services) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)/api/health" -TimeoutSec 3 -ErrorAction Stop
            Write-Host "  [OK] $($svc.Name) -- healthy"
        } catch {
            Write-Host "  [FAIL] $($svc.Name) -- not responding"
        }
    }

    Write-Host ""
    Write-Host "  All services are ready!"
    Write-Host ""
    Write-Host "  To stop:   .\start_backends.ps1 -Stop"
    Write-Host "  To demo:   .\venv\Scripts\python.exe demo_lockdown.py"
    Write-Host ""
}

if ($Stop) {
    Stop-AllServices
} else {
    Start-AllServices
}
