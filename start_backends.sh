#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║  PhishGuard — Backend Services Launcher (Linux/macOS)       ║
# ║  Starts PhishGuard + SecurBank + BreezeTech in background   ║
# ╚══════════════════════════════════════════════════════════════╝
#
# Usage:
#   ./start_backends.sh          # Start all services
#   ./start_backends.sh stop     # Stop all services
#   ./start_backends.sh status   # Check service status
#

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

# ─── ANSI colors ─────────────────────────────────────────────
G='\033[92m'   # Green
R='\033[91m'   # Red
C='\033[96m'   # Cyan
Y='\033[93m'   # Yellow
B='\033[1m'    # Bold
D='\033[90m'   # Dim
X='\033[0m'    # Reset

# ─── Service definitions ─────────────────────────────────────
declare -a SVC_NAMES=("PhishGuard" "SecurBank" "BreezeTech")
declare -a SVC_PORTS=(8000 9000 9001)
declare -a SVC_CWDS=("$ROOT" "$ROOT/mockups/bankingapp" "$ROOT/mockups/startup")
declare -a SVC_PIDS=("$ROOT/.pid_phishguard" "$ROOT/.pid_securbank" "$ROOT/.pid_breezetech")
declare -a SVC_LOGS=("$ROOT/.log_phishguard" "$ROOT/.log_securbank" "$ROOT/.log_breezetech")

banner() {
    echo ""
    echo -e "${C}╔══════════════════════════════════════════════════════════════╗${X}"
    echo -e "${C}║  ${B}🛡  PhishGuard — Backend Services Launcher${X}${C}                 ║${X}"
    echo -e "${C}╚══════════════════════════════════════════════════════════════╝${X}"
    echo ""
}

# ─── Find the python executable ───────────────────────────────
find_python() {
    local cwd="$1"
    if [ -f "$cwd/venv/bin/python" ]; then
        echo "$cwd/venv/bin/python"
    elif [ -f "$cwd/venv/bin/python3" ]; then
        echo "$cwd/venv/bin/python3"
    elif command -v python3 &>/dev/null; then
        echo "python3"
    else
        echo "python"
    fi
}

# ─── Stop all services ───────────────────────────────────────
stop_all() {
    banner
    echo -e "  ${Y}Stopping all services...${X}"
    echo ""

    for i in "${!SVC_NAMES[@]}"; do
        local name="${SVC_NAMES[$i]}"
        local pidfile="${SVC_PIDS[$i]}"
        local port="${SVC_PORTS[$i]}"

        if [ -f "$pidfile" ]; then
            local pid
            pid=$(cat "$pidfile" 2>/dev/null)
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
                # Wait briefly for graceful shutdown
                sleep 0.5
                # Force kill if still alive
                kill -9 "$pid" 2>/dev/null || true
                echo -e "  ${G}✓${X} $name (PID $pid) stopped"
            else
                echo -e "  ${D}ℹ${X} $name (PID $pid) was not running"
            fi
            rm -f "$pidfile"
        else
            echo -e "  ${D}ℹ${X} $name — no PID file found"
        fi

        # Fallback: kill anything still on the port
        local port_pid
        port_pid=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$port_pid" ]; then
            kill -9 $port_pid 2>/dev/null || true
            echo -e "  ${Y}⚠${X} Killed leftover process on port $port"
        fi
    done

    echo ""
    echo -e "  ${G}All services stopped.${X}"
    echo ""
}

# ─── Check service status ────────────────────────────────────
status_all() {
    banner
    echo -e "  ${B}Service Status:${X}"
    echo ""

    for i in "${!SVC_NAMES[@]}"; do
        local name="${SVC_NAMES[$i]}"
        local port="${SVC_PORTS[$i]}"
        local pidfile="${SVC_PIDS[$i]}"
        local status_icon="${R}✗${X}"
        local status_text="${R}offline${X}"

        if [ -f "$pidfile" ]; then
            local pid
            pid=$(cat "$pidfile" 2>/dev/null)
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                # Try health check
                if curl -sf "http://localhost:$port/api/health" >/dev/null 2>&1; then
                    status_icon="${G}✓${X}"
                    status_text="${G}healthy${X} (PID $pid)"
                else
                    status_icon="${Y}⚠${X}"
                    status_text="${Y}running but not responding${X} (PID $pid)"
                fi
            fi
        fi

        echo -e "  $status_icon $name (port $port) — $status_text"
    done

    echo ""
}

# ─── Start all services ──────────────────────────────────────
start_all() {
    banner

    # Check for existing processes and stop them first
    local any_running=false
    for i in "${!SVC_PORTS[@]}"; do
        if lsof -ti :"${SVC_PORTS[$i]}" >/dev/null 2>&1; then
            any_running=true
            break
        fi
    done

    if $any_running; then
        echo -e "  ${Y}⚠ Existing services detected — stopping them first...${X}"
        stop_all
        sleep 1
        banner
    fi

    echo -e "  Starting backend services..."
    echo ""

    for i in "${!SVC_NAMES[@]}"; do
        local name="${SVC_NAMES[$i]}"
        local port="${SVC_PORTS[$i]}"
        local cwd="${SVC_CWDS[$i]}"
        local pidfile="${SVC_PIDS[$i]}"
        local logfile="${SVC_LOGS[$i]}"

        local python
        python=$(find_python "$cwd")

        if [ ! -f "$python" ] && ! command -v "$python" &>/dev/null; then
            echo -e "  ${R}✗${X} $name: python not found"
            continue
        fi

        # Start in background, redirect output to log file
        cd "$cwd"
        nohup "$python" -m backend.main > "$logfile" 2>&1 &
        local pid=$!
        echo "$pid" > "$pidfile"
        cd "$ROOT"

        echo -e "  ${G}✓${X} $name started (PID $pid) → ${C}http://localhost:$port${X}"
    done

    # Wait for services to initialize
    echo ""
    echo -e "  ${D}Waiting for services to initialize...${X}"
    sleep 3

    # Health checks
    echo ""
    echo -e "  ${B}Health Checks:${X}"
    for i in "${!SVC_NAMES[@]}"; do
        local name="${SVC_NAMES[$i]}"
        local port="${SVC_PORTS[$i]}"

        if curl -sf "http://localhost:$port/api/health" >/dev/null 2>&1; then
            echo -e "  ${G}✓${X} $name — ${G}healthy${X}"
        else
            echo -e "  ${R}✗${X} $name — ${R}not responding${X}"
        fi
    done

    echo ""
    echo -e "  ${G}${B}All services are ready!${X}"
    echo ""
    echo -e "  ${D}To stop:   ./start_backends.sh stop${X}"
    echo -e "  ${D}To status: ./start_backends.sh status${X}"
    echo -e "  ${D}To demo:   python3 demo_lockdown.py${X}"
    echo ""
}

# ─── Main ─────────────────────────────────────────────────────
case "${1:-start}" in
    stop)
        stop_all
        ;;
    status)
        status_all
        ;;
    start|"")
        start_all
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
