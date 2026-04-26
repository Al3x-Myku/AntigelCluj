# ╔══════════════════════════════════════════════════════════════╗
# ║  PhishGuard — Backend Services Launcher (Windows)           ║
# ║  Starts PhishGuard + SecurBank + BreezeTech in background   ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Usage:
#   .\start_backends.ps1          # Start all services
#   .\start_backends.ps1 -Stop    # Stop all services
#

param(
    [switch]$Stop
)

$ROOT = $PSScriptRoot

# ─── Service definitions ─────────────────────────────────────
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

# ─── ANSI colors ─────────────────────────────────────────────
$G = "`e[92m"   # Green
$R = "`e[91m"   # Red
$C = "`e[96m"   # Cyan
$Y = "`e[93m"   # Yellow
$B = "`e[1m"    # Bold
$D = "`e[90m"   # Dim
$X = "`e[0m"    # Reset

function Write-Banner {
    Write-Host ""
    Write-Host "${C}╔══════════════════════════════════════════════════════════════╗${X}"
    Write-Host "${C}║  ${B}🛡  PhishGuard — Backend Services Launcher${X}${C}                 ║${X}"
    Write-Host "${C}╚══════════════════════════════════════════════════════════════╝${X}"
    Write-Host ""
}

# ─── Stop all services ───────────────────────────────────────
function Stop-AllServices {
    Write-Banner
    Write-Host "  ${Y}Stopping all services...${X}"
    Write-Host ""

    foreach ($svc in $services) {
        if (Test-Path $svc.PidFile) {
            $pid = Get-Content $svc.PidFile -ErrorAction SilentlyContinue
            if ($pid) {
                try {
                    # Kill the process tree
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    # Also kill any children
                    Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $pid } | ForEach-Object {
                        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                    }
                    Write-Host "  ${G}✓${X} $($svc.Name) (PID $pid) stopped"
                } catch {
                    Write-Host "  ${D}ℹ${X} $($svc.Name) (PID $pid) was not running"
                }
            }
            Remove-Item $svc.PidFile -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host "  ${D}ℹ${X} $($svc.Name) — no PID file found"
        }
    }

    # Fallback: kill anything still on the ports
    foreach ($svc in $services) {
        $portListeners = Get-NetTCPConnection -LocalPort $svc.Port -ErrorAction SilentlyContinue
        foreach ($conn in $portListeners) {
            if ($conn.State -eq "Listen") {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Host "  ${Y}⚠${X} Killed leftover process on port $($svc.Port)"
            }
        }
    }

    Write-Host ""
    Write-Host "  ${G}All services stopped.${X}"
    Write-Host ""
}

# ─── Start all services ──────────────────────────────────────
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
        Write-Host "  ${Y}⚠ Existing services detected — stopping them first...${X}"
        Stop-AllServices
        Start-Sleep -Seconds 1
        Write-Banner
    }

    Write-Host "  Starting backend services..."
    Write-Host ""

    foreach ($svc in $services) {
        # Check venv exists
        if (-not (Test-Path $svc.Venv)) {
            Write-Host "  ${R}✗${X} $($svc.Name): venv not found at $($svc.Venv)"
            continue
        }

        # Start the process in background
        $proc = Start-Process -FilePath $svc.Venv `
            -ArgumentList "-m", "backend.main" `
            -WorkingDirectory $svc.Cwd `
            -WindowStyle Hidden `
            -PassThru

        # Save PID
        $proc.Id | Out-File -FilePath $svc.PidFile -NoNewline

        Write-Host "  ${G}✓${X} $($svc.Name) started (PID $($proc.Id)) → ${C}http://localhost:$($svc.Port)${X}"
    }

    # Wait a moment for services to initialize
    Write-Host ""
    Write-Host "  ${D}Waiting for services to initialize...${X}"
    Start-Sleep -Seconds 3

    # Health checks
    Write-Host ""
    Write-Host "  ${B}Health Checks:${X}"
    foreach ($svc in $services) {
        try {
            $response = Invoke-RestMethod -Uri "http://localhost:$($svc.Port)/api/health" -TimeoutSec 3 -ErrorAction Stop
            Write-Host "  ${G}✓${X} $($svc.Name) — ${G}healthy${X}"
        } catch {
            Write-Host "  ${R}✗${X} $($svc.Name) — ${R}not responding${X}"
        }
    }

    Write-Host ""
    Write-Host "  ${G}${B}All services are ready!${X}"
    Write-Host ""
    Write-Host "  ${D}To stop:   .\start_backends.ps1 -Stop${X}"
    Write-Host "  ${D}To demo:   .\venv\Scripts\python.exe demo_lockdown.py${X}"
    Write-Host ""
}

# ─── Main ─────────────────────────────────────────────────────
if ($Stop) {
    Stop-AllServices
} else {
    Start-AllServices
}
