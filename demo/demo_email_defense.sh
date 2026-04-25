#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PhishGuard — Email Defense Demo
# ═══════════════════════════════════════════════════════════════
# Demonstrates the email defense pipeline:
#   1. Scan a known phishing email (manual test)
#   2. Scan all captured emails from disk
#   3. Show quarantine list
#   4. Delete flagged emails
#   5. Print detection/prevention stats

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  📧 Email Defense Demo${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# ── 1. Test: Scan a Known Phishing Email ─────────────────────
echo -e "${BLUE}▶ Test 1: Scan a known phishing email${NC}"
PHISH_RESULT=$(curl -s -X POST "${BASE_URL}/api/defense/email/scan" \
    -H "Content-Type: application/json" \
    -d '{
        "subject": "URGENT: Your account has been suspended - Verify immediately",
        "body": "Dear Customer,\n\nWe have detected unusual activity on your bank account. Your account will be terminated within 24 hours unless you verify your identity.\n\nClick here to verify: http://192.168.1.100/verify?token=abc123\n\nFailure to comply will result in permanent suspension.\n\nSecureBank Security Team\nsecurity@securebank-verify.com",
        "from_addr": "security@securebank-verify.com",
        "to_addr": "victim@company.com",
        "reply_to": "attacker@gmail.com"
    }' 2>/dev/null)

SCORE=$(echo "$PHISH_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('verdict',{}).get('score',0))" 2>/dev/null)
RISK=$(echo "$PHISH_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('verdict',{}).get('risk_level','?'))" 2>/dev/null)
QUARANTINED=$(echo "$PHISH_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('quarantined',False))" 2>/dev/null)
FLAGS=$(echo "$PHISH_RESULT" | python3 -c "import sys,json; flags=json.load(sys.stdin).get('verdict',{}).get('flags',[]); [print(f'    ⚠ {f}') for f in flags]" 2>/dev/null)

echo -e "  Score:       ${BOLD}${SCORE}${NC}"
echo -e "  Risk Level:  ${BOLD}${RED}${RISK}${NC}"
echo -e "  Quarantined: ${QUARANTINED}"
echo -e "  Flags:"
echo "$FLAGS"

# ── 2. Test: Scan a Safe Email ───────────────────────────────
echo -e "\n${BLUE}▶ Test 2: Scan a legitimate email${NC}"
SAFE_RESULT=$(curl -s -X POST "${BASE_URL}/api/defense/email/scan" \
    -H "Content-Type: application/json" \
    -d '{
        "subject": "Meeting tomorrow at 10 AM",
        "body": "Hi team,\n\nJust a reminder that we have our weekly standup tomorrow at 10 AM in the conference room.\n\nPlease prepare your updates.\n\nBest,\nJohn",
        "from_addr": "john@company.com",
        "to_addr": "team@company.com"
    }' 2>/dev/null)

SAFE_SCORE=$(echo "$SAFE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('verdict',{}).get('score',0))" 2>/dev/null)
SAFE_RISK=$(echo "$SAFE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('verdict',{}).get('risk_level','?'))" 2>/dev/null)
echo -e "  Score:       ${BOLD}${SAFE_SCORE}${NC}"
echo -e "  Risk Level:  ${BOLD}${GREEN}${SAFE_RISK}${NC}"

# ── 3. Scan All Captured Emails ──────────────────────────────
echo -e "\n${BLUE}▶ Scanning all captured emails from disk...${NC}"
SCAN_CAP=$(curl -s -X POST "${BASE_URL}/api/defense/email/scan-captured" 2>/dev/null)
SCANNED=$(echo "$SCAN_CAP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scanned',0))" 2>/dev/null)
FLAGGED=$(echo "$SCAN_CAP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('flagged',0))" 2>/dev/null)
echo -e "  ${GREEN}✓${NC} Scanned: ${SCANNED} | Flagged: ${RED}${FLAGGED}${NC}"

# Show flagged results
echo "$SCAN_CAP" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = [r for r in data.get('results', []) if r.get('risk_level') in ('suspicious','dangerous')]
for r in results[:10]:
    risk = r.get('risk_level','?').upper()
    score = r.get('score', 0)
    subj = r.get('subject','')[:40]
    frm = r.get('from','')[:30]
    print(f'    [{risk:10s}] score={score:.2f} | {frm} | {subj}')
" 2>/dev/null || true

# ── 4. Show Quarantine ───────────────────────────────────────
echo -e "\n${BLUE}▶ Current Quarantine:${NC}"
QUAR=$(curl -s "${BASE_URL}/api/defense/email/quarantine?status=quarantined" 2>/dev/null)
Q_COUNT=$(echo "$QUAR" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total',0))" 2>/dev/null)
echo -e "  ${YELLOW}${Q_COUNT}${NC} emails in quarantine"

# ── 5. Delete All Flagged ────────────────────────────────────
echo -e "\n${BLUE}▶ Deleting all flagged emails...${NC}"
DEL=$(curl -s -X POST "${BASE_URL}/api/defense/email/delete-all-flagged" 2>/dev/null)
DELETED=$(echo "$DEL" | python3 -c "import sys,json; print(json.load(sys.stdin).get('deleted',0))" 2>/dev/null)
echo -e "  ${GREEN}✓${NC} ${DELETED} emails deleted from recipient mailboxes"

# ── 6. Final Stats ───────────────────────────────────────────
echo -e "\n${BLUE}▶ Email Defense Statistics:${NC}"
STATS=$(curl -s "${BASE_URL}/api/defense/email/stats" 2>/dev/null)
echo "$STATS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'  Total Scanned:    {d.get(\"total_scanned\",0)}')
print(f'  Quarantined:      {d.get(\"quarantined\",0)}')
print(f'  Dangerous:        {d.get(\"dangerous\",0)}')
print(f'  Deleted:          {d.get(\"deleted\",0)}')
print(f'  Released:         {d.get(\"released\",0)}')
print(f'  Prevention Rate:  {d.get(\"prevention_rate\",0)}%')
" 2>/dev/null

echo -e "\n${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}✓ Email defense demo complete!${NC}"
echo -e "  ${BLUE}Dashboard: ${BASE_URL}/defense/email-scanner${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
