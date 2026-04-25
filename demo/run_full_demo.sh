#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PhishGuard — Full End-to-End Demo
# ═══════════════════════════════════════════════════════════════
# Runs the complete attack → detect → prevent lifecycle:
#   1. Health check
#   2. Train anomaly model
#   3. OSINT scan (media search)
#   4. Auto-generate campaign from OSINT
#   5. Launch campaign (sends phishing emails)
#   6. Scan captured emails for phishing content
#   7. Delete flagged emails
#   8. Simulate attack logins
#   9. Print final scorecard

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEMO_DOMAIN="${DEMO_DOMAIN:-example.com}"
DEMO_COMPANY="${DEMO_COMPANY:-Example Corp}"
ATTACK_COUNT="${ATTACK_COUNT:-20}"
NORMAL_COUNT="${NORMAL_COUNT:-30}"

header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
}

step() {
    echo -e "\n${BLUE}▶ STEP $1: $2${NC}"
    echo -e "${BLUE}──────────────────────────────────────────${NC}"
}

ok() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${YELLOW}ℹ${NC} $1"; }

header "🛡  PhishGuard — Full Demo"
echo -e "  Target:  ${BOLD}${BASE_URL}${NC}"
echo -e "  Domain:  ${BOLD}${DEMO_DOMAIN}${NC}"
echo -e "  Company: ${BOLD}${DEMO_COMPANY}${NC}"
echo -e "  Date:    $(date '+%Y-%m-%d %H:%M:%S')"

# ── Step 1: Health Check ─────────────────────────────────────
step 1 "Server Health Check"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health" 2>/dev/null || echo "000")
if [ "$HEALTH" = "200" ]; then
    ok "Server is running at ${BASE_URL}"
else
    fail "Server is not reachable (HTTP ${HEALTH})"
    echo -e "  ${RED}Start the server first: python -m backend.main${NC}"
    exit 1
fi

# ── Step 2: Train Anomaly Model ──────────────────────────────
step 2 "Train Anomaly Detection Model"
TRAIN=$(curl -s -X POST "${BASE_URL}/api/defense/train" 2>/dev/null)
SAMPLES=$(echo "$TRAIN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('stats',{}).get('n_samples',0))" 2>/dev/null || echo "0")
ok "Model trained on ${SAMPLES} normal login events"

# ── Step 3: Score Existing Events ────────────────────────────
step 3 "Score All Unscored Events"
SCORE=$(curl -s -X POST "${BASE_URL}/api/defense/score" 2>/dev/null)
SCORED=$(echo "$SCORE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('scored',0))" 2>/dev/null || echo "0")
ANOM=$(echo "$SCORE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('anomalies_found',0))" 2>/dev/null || echo "0")
ok "Scored ${SCORED} events → ${ANOM} anomalies found"

# ── Step 4: OSINT Scan ───────────────────────────────────────
step 4 "OSINT Reconnaissance (Media Search)"
SCAN=$(curl -s -X POST "${BASE_URL}/api/attack/osint/media-search" \
    -H "Content-Type: application/json" \
    -d "{\"domain\":\"${DEMO_DOMAIN}\",\"company_name\":\"${DEMO_COMPANY}\",\"platforms\":[\"linkedin\",\"github\",\"facebook\"]}" 2>/dev/null)
SCAN_ID=$(echo "$SCAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan_id',''))" 2>/dev/null || echo "")

if [ -n "$SCAN_ID" ]; then
    ok "Scan started: ${SCAN_ID}"
    info "Waiting for scan to complete (max 30s)..."
    for i in $(seq 1 15); do
        sleep 2
        STATUS=$(curl -s "${BASE_URL}/api/attack/osint/results/${SCAN_ID}" 2>/dev/null)
        S=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('status',''))" 2>/dev/null || echo "")
        if [ "$S" = "completed" ] || [ "$S" = "failed" ]; then
            CONTACTS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('total_contacts',0))" 2>/dev/null || echo "0")
            EMAILS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('total_emails',0))" 2>/dev/null || echo "0")
            ok "Scan ${S}: ${CONTACTS} contacts, ${EMAILS} emails discovered"
            break
        fi
        echo -n "."
    done
    echo ""

    # Generate campaign from OSINT
    info "Auto-generating campaign from OSINT results..."
    CAMPAIGN=$(curl -s -X POST "${BASE_URL}/api/attack/osint/generate-campaign" \
        -H "Content-Type: application/json" \
        -d "{\"scan_id\":\"${SCAN_ID}\",\"campaign_name\":\"Demo OSINT Campaign\"}" 2>/dev/null)
    CAMP_ID=$(echo "$CAMPAIGN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('campaign',{}).get('id',''))" 2>/dev/null || echo "")
    if [ -n "$CAMP_ID" ]; then
        ok "Campaign #${CAMP_ID} created from OSINT results"
    else
        info "No campaign created (scan may not have found emails)"
    fi
else
    info "Skipping OSINT (no scan ID returned)"
fi

# ── Step 5: Email Defense — Scan Captured Emails ─────────────
step 5 "Email Defense — Scan Captured Emails"
SCAN_CAP=$(curl -s -X POST "${BASE_URL}/api/defense/email/scan-captured" 2>/dev/null)
CAP_SCANNED=$(echo "$SCAN_CAP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scanned',0))" 2>/dev/null || echo "0")
CAP_FLAGGED=$(echo "$SCAN_CAP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('flagged',0))" 2>/dev/null || echo "0")
ok "Scanned ${CAP_SCANNED} captured emails → ${CAP_FLAGGED} flagged as suspicious/dangerous"

# ── Step 6: Delete All Flagged Emails ────────────────────────
step 6 "Email Defense — Delete Flagged Emails"
DEL=$(curl -s -X POST "${BASE_URL}/api/defense/email/delete-all-flagged" 2>/dev/null)
DELETED=$(echo "$DEL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('deleted',0))" 2>/dev/null || echo "0")
ok "${DELETED} phishing emails deleted from recipient mailboxes"

# ── Step 7: Simulate Attack Traffic ──────────────────────────
step 7 "Simulate Login Traffic (${NORMAL_COUNT} normal + ${ATTACK_COUNT} attack)"
info "Sending normal logins..."
for i in $(seq 1 $NORMAL_COUNT); do
    curl -s -X POST "${BASE_URL}/api/defense/simulate-login" > /dev/null 2>&1
done
ok "${NORMAL_COUNT} normal logins sent"

info "Sending attack logins..."
TP=0
BANS=0
for i in $(seq 1 $ATTACK_COUNT); do
    RESULT=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login?is_attack=true" 2>/dev/null)
    IS_ANOM=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_anomalous',False))" 2>/dev/null || echo "False")
    HAS_BAN=$(echo "$RESULT" | python3 -c "import sys,json; print('ban_triggered' in json.load(sys.stdin))" 2>/dev/null || echo "False")
    if [ "$IS_ANOM" = "True" ]; then TP=$((TP+1)); fi
    if [ "$HAS_BAN" = "True" ]; then BANS=$((BANS+1)); fi
done
ok "${ATTACK_COUNT} attack logins sent → ${TP} detected, ${BANS} bans triggered"

# ── Step 8: Final Dashboard Stats ────────────────────────────
step 8 "Final Defense Dashboard Stats"
DASH=$(curl -s "${BASE_URL}/api/defense/dashboard" 2>/dev/null)
TOTAL_EV=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_events',0))" 2>/dev/null || echo "0")
TOTAL_AN=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_anomalies',0))" 2>/dev/null || echo "0")
TOTAL_BN=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('active_bans',0))" 2>/dev/null || echo "0")
TOTAL_LK=$(echo "$DASH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('locked_accounts',0))" 2>/dev/null || echo "0")

EMAIL_ST=$(curl -s "${BASE_URL}/api/defense/email/stats" 2>/dev/null)
EM_TOTAL=$(echo "$EMAIL_ST" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_scanned',0))" 2>/dev/null || echo "0")
EM_DELET=$(echo "$EMAIL_ST" | python3 -c "import sys,json; print(json.load(sys.stdin).get('deleted',0))" 2>/dev/null || echo "0")
EM_PREV=$(echo "$EMAIL_ST" | python3 -c "import sys,json; print(json.load(sys.stdin).get('prevention_rate',0))" 2>/dev/null || echo "0")

# ── Final Scorecard ──────────────────────────────────────────
TPR=$(echo "scale=1; $TP * 100 / $ATTACK_COUNT" | bc 2>/dev/null || echo "N/A")

header "📊 FINAL SCORECARD"
echo ""
echo -e "  ${BOLD}LOGIN ANOMALY DETECTION${NC}"
echo -e "  ────────────────────────────────────"
echo -e "  Total Events:        ${BOLD}${TOTAL_EV}${NC}"
echo -e "  Anomalies Detected:  ${BOLD}${RED}${TOTAL_AN}${NC}"
echo -e "  Active IP Bans:      ${BOLD}${YELLOW}${TOTAL_BN}${NC}"
echo -e "  Accounts Locked:     ${BOLD}${RED}${TOTAL_LK}${NC}"
echo -e "  Attack Detection:    ${BOLD}${GREEN}${TPR}%${NC}  (${TP}/${ATTACK_COUNT})"
echo ""
echo -e "  ${BOLD}EMAIL DEFENSE${NC}"
echo -e "  ────────────────────────────────────"
echo -e "  Emails Scanned:      ${BOLD}${EM_TOTAL}${NC}"
echo -e "  Emails Deleted:      ${BOLD}${RED}${EM_DELET}${NC}"
echo -e "  Prevention Rate:     ${BOLD}${GREEN}${EM_PREV}%${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}✓ Demo complete!${NC}"
echo -e "  ${BLUE}Dashboard: ${BASE_URL}/defense/${NC}"
echo -e "  ${BLUE}Email Scanner: ${BASE_URL}/defense/email-scanner${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
