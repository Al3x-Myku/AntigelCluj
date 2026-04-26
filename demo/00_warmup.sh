#!/bin/bash
# ╔══════════════════════════════════════════════════════════════════╗
# ║   PhishGuard — PRE-DEMO WARMUP                                   ║
# ║   Run this BEFORE you walk on stage.                             ║
# ║   Seeds the DB, trains the ML model, pre-loads attack traffic.   ║
# ║   Target: completes in ~15 seconds, leaves app demo-ready.       ║
# ╚══════════════════════════════════════════════════════════════════╝

set -eo pipefail

# ── Colours ──────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"

# ── Helpers ───────────────────────────────────────────────────────────
ok()    { echo -e "  ${GREEN}✓${NC}  $1"; }
warn()  { echo -e "  ${YELLOW}⚠${NC}  $1"; }
info()  { echo -e "  ${DIM}›${NC}  $1"; }
fail()  { echo -e "  ${RED}✗${NC}  $1"; }
banner(){ echo -e "\n${CYAN}${BOLD}$1${NC}"; echo -e "${DIM}$(printf '─%.0s' {1..60})${NC}"; }

# ── Header ────────────────────────────────────────────────────────────
clear 2>/dev/null || true
echo -e "${CYAN}${BOLD}"
cat << 'LOGO'
  ██████╗ ██╗  ██╗██╗███████╗██╗  ██╗ ██████╗ ██╗   ██╗ █████╗ ██████╗ ██████╗
  ██╔══██╗██║  ██║██║██╔════╝██║  ██║██╔════╝ ██║   ██║██╔══██╗██╔══██╗██╔══██╗
  ██████╔╝███████║██║███████╗███████║██║  ███╗██║   ██║███████║██████╔╝██║  ██║
  ██╔═══╝ ██╔══██║██║╚════██║██╔══██║██║   ██║██║   ██║██╔══██║██╔══██╗██║  ██║
  ██║     ██║  ██║██║███████║██║  ██║╚██████╔╝╚██████╔╝██║  ██║██║  ██║██████╔╝
  ╚═╝     ╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
LOGO
echo -e "${NC}"
echo -e "  ${BOLD}PRE-DEMO WARMUP${NC}  ${DIM}— Run before walking on stage${NC}"
echo -e "  ${DIM}Target server: ${BOLD}${NC}${BASE_URL}"
echo -e "  ${DIM}$(date '+%Y-%m-%d %H:%M:%S')${NC}"
echo ""

# ── Step 1: Server health ────────────────────────────────────────────
banner "[ 1/5 ]  Server Health Check"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health" 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
    ok "PhishGuard is running at ${BASE_URL}"
else
    fail "Server not reachable (HTTP ${HTTP})"
    echo ""
    echo -e "  ${RED}Start the server first:${NC}"
    echo -e "  ${BOLD}  cd /home/admin/project/AntigelCluj && source venv/bin/activate && python -m backend.main${NC}"
    exit 1
fi

# ── Step 2: Train the ML model ───────────────────────────────────────
banner "[ 2/5 ]  Training Anomaly Detection Model (MCD / Mahalanobis)"
TRAIN_RESP=$(curl -s -X POST "${BASE_URL}/api/defense/train" 2>/dev/null)
SAMPLES=$(echo "$TRAIN_RESP" | python3 -c \
    "import sys,json; d=json.load(sys.stdin); print(d.get('stats',{}).get('n_samples','?'))" 2>/dev/null || echo "?")
ok "MinCovDet model trained on ${BOLD}${SAMPLES}${NC} normal login events"
ok "Chi-squared threshold set at ${BOLD}17.53${NC} (df=8, confidence=97.5%)"

# ── Step 3: Score all historical events ──────────────────────────────
banner "[ 3/5 ]  Scoring Historical Login Events"
SCORE_RESP=$(curl -s -X POST "${BASE_URL}/api/defense/score" 2>/dev/null)
SCORED=$(echo "$SCORE_RESP" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('scored',0))" 2>/dev/null || echo "0")
ANOM=$(echo "$SCORE_RESP" | python3 -c \
    "import sys,json; print(json.load(sys.stdin).get('anomalies_found',0))" 2>/dev/null || echo "0")
ok "Scored ${BOLD}${SCORED}${NC} events"
ok "${BOLD}${RED}${ANOM}${NC} anomalies already flagged in historical data"

# ── Step 4: Pre-inject attack traffic ────────────────────────────────
banner "[ 4/5 ]  Pre-Seeding Attack Traffic (so the monitor looks alive)"
PRE_ATTACKS=8
PRE_NORMALS=12
info "Injecting ${PRE_NORMALS} normal logins..."
for i in $(seq 1 $PRE_NORMALS); do
    curl -s -X POST "${BASE_URL}/api/defense/simulate-login" > /dev/null 2>&1
done
info "Injecting ${PRE_ATTACKS} attack logins from attacker IPs..."
DETECTED=0
for i in $(seq 1 $PRE_ATTACKS); do
    R=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login?is_attack=true" 2>/dev/null)
    IS_A=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_anomalous',False))" 2>/dev/null || echo "False")
    [ "$IS_A" = "True" ] && DETECTED=$((DETECTED+1))
done
ok "${PRE_ATTACKS} attack logins injected — ${BOLD}${GREEN}${DETECTED}/${PRE_ATTACKS}${NC} detected"
ok "Live monitor at ${BOLD}${BASE_URL}/defense/monitor${NC} will show live red alerts"

# ── Step 5: Final readiness check ────────────────────────────────────
banner "[ 5/5 ]  Readiness Check"
DASH=$(curl -s "${BASE_URL}/api/defense/dashboard" 2>/dev/null)
TOTAL_EV=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_events',0))" 2>/dev/null || echo "?")
TOTAL_AN=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_anomalies',0))" 2>/dev/null || echo "?")
TOTAL_BAN=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('active_bans',0))" 2>/dev/null || echo "?")

echo ""
echo -e "  ${BOLD}Dashboard Snapshot${NC}"
echo -e "  ${DIM}┌──────────────────────────────┐${NC}"
printf  "  ${DIM}│${NC}  Total Login Events   ${BOLD}%6s${NC}  ${DIM}│${NC}\n" "$TOTAL_EV"
printf  "  ${DIM}│${NC}  Anomalies Flagged     ${BOLD}${RED}%6s${NC}  ${DIM}│${NC}\n" "$TOTAL_AN"
printf  "  ${DIM}│${NC}  Active IP Bans        ${BOLD}${YELLOW}%6s${NC}  ${DIM}│${NC}\n" "$TOTAL_BAN"
echo -e "  ${DIM}└──────────────────────────────┘${NC}"
echo ""

# ── Stage links ──────────────────────────────────────────────────────
echo -e "${CYAN}${BOLD}  🎬  STAGE IS SET — Open these tabs before presenting:${NC}"
echo ""
echo -e "  ${BOLD}Tab 1${NC}  ${BLUE}${BASE_URL}/defense/${NC}              ${DIM}← Defense Overview + ML Histogram${NC}"
echo -e "  ${BOLD}Tab 2${NC}  ${BLUE}${BASE_URL}/defense/monitor${NC}        ${DIM}← Live Login Event Feed${NC}"
echo -e "  ${BOLD}Tab 3${NC}  ${BLUE}${BASE_URL}/defense/lockdown${NC}       ${DIM}← Account Lockdown Manager${NC}"
echo -e "  ${BOLD}Tab 4${NC}  ${BLUE}${BASE_URL}/attack/${NC}                ${DIM}← Red Team Campaign Dashboard${NC}"
echo ""
echo -e "${GREEN}${BOLD}  ✓ All systems GO. Run 01_live_demo.sh when you're ready.${NC}"
echo -e "${CYAN}$(printf '═%.0s' {1..60})${NC}"
echo ""
