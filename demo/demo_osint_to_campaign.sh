#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PhishGuard — OSINT → Campaign Demo
# ═══════════════════════════════════════════════════════════════
# Demonstrates the offense pipeline:
#   1. Run OSINT scan on a target domain
#   2. Wait for completion, show discovered contacts
#   3. Auto-generate campaign from results
#   4. Launch campaign
#   5. Show campaign stats

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"
TARGET_DOMAIN="${1:-example.com}"
COMPANY_NAME="${2:-Example Corp}"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  ⚔  OSINT → Campaign Pipeline Demo${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Target Domain:  ${BOLD}${TARGET_DOMAIN}${NC}"
echo -e "  Company:        ${BOLD}${COMPANY_NAME}${NC}"
echo ""

# ── 1. Run OSINT Scan ────────────────────────────────────────
echo -e "${BLUE}▶ Starting OSINT Media Search...${NC}"
SCAN=$(curl -s -X POST "${BASE_URL}/api/attack/osint/media-search" \
    -H "Content-Type: application/json" \
    -d "{\"domain\":\"${TARGET_DOMAIN}\",\"company_name\":\"${COMPANY_NAME}\",\"platforms\":[\"linkedin\",\"facebook\",\"github\",\"instagram\"]}" 2>/dev/null)
SCAN_ID=$(echo "$SCAN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan_id',''))" 2>/dev/null)

if [ -z "$SCAN_ID" ]; then
    echo -e "  ${RED}✗ Failed to start scan${NC}"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Scan started: ${SCAN_ID}"

# ── 2. Wait for Completion ───────────────────────────────────
echo -e "\n${BLUE}▶ Waiting for scan to complete...${NC}"
for i in $(seq 1 30); do
    sleep 2
    STATUS=$(curl -s "${BASE_URL}/api/attack/osint/results/${SCAN_ID}" 2>/dev/null)
    S=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('status',''))" 2>/dev/null)
    if [ "$S" = "completed" ] || [ "$S" = "failed" ]; then
        break
    fi
    echo -n "."
done
echo ""

# ── 3. Show Results ──────────────────────────────────────────
CONTACTS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('total_contacts',0))" 2>/dev/null)
EMAILS=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('total_emails',0))" 2>/dev/null)
PHONES=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('total_phones',0))" 2>/dev/null)
DURATION=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('scan',{}).get('duration_seconds',0))" 2>/dev/null)

echo -e "${BLUE}▶ OSINT Results:${NC}"
echo -e "  Status:    ${GREEN}${S}${NC}"
echo -e "  Contacts:  ${BOLD}${CONTACTS}${NC}"
echo -e "  Emails:    ${BOLD}${EMAILS}${NC}"
echo -e "  Phones:    ${BOLD}${PHONES}${NC}"
echo -e "  Duration:  ${DURATION}s"

# Show first 10 results
echo -e "\n${BLUE}▶ Top Discovered Contacts:${NC}"
echo "$STATUS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])[:10]
for i, r in enumerate(results):
    name = f\"{r.get('first_name','')} {r.get('last_name','')}\".strip() or '—'
    email = r.get('email', '') or '—'
    dept = r.get('department', '') or '—'
    risk = r.get('risk_score', 0)
    src = r.get('source_url', '')[:40]
    print(f'  {i+1:2d}. {name:<20s} | {email:<35s} | {dept:<12s} | risk={risk:.2f} | {src}')
" 2>/dev/null || echo "  (no results to display)"

# ── 4. Generate Campaign ─────────────────────────────────────
echo -e "\n${BLUE}▶ Auto-generating phishing campaign...${NC}"
CAMPAIGN=$(curl -s -X POST "${BASE_URL}/api/attack/osint/generate-campaign" \
    -H "Content-Type: application/json" \
    -d "{\"scan_id\":\"${SCAN_ID}\",\"campaign_name\":\"OSINT Demo — ${COMPANY_NAME}\"}" 2>/dev/null)
CAMP_ID=$(echo "$CAMPAIGN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('campaign',{}).get('id',''))" 2>/dev/null)

if [ -n "$CAMP_ID" ] && [ "$CAMP_ID" != "None" ] && [ "$CAMP_ID" != "" ]; then
    TARGETS=$(echo "$CAMPAIGN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('campaign',{}).get('stats',{}).get('total_targets',0))" 2>/dev/null)
    echo -e "  ${GREEN}✓${NC} Campaign #${CAMP_ID} created with ${TARGETS} targets"

    # ── 5. Launch Campaign ───────────────────────────────────
    echo -e "\n${BLUE}▶ Launching campaign...${NC}"
    LAUNCH=$(curl -s -X POST "${BASE_URL}/api/attack/campaigns/${CAMP_ID}/launch" 2>/dev/null)
    LSTATUS=$(echo "$LAUNCH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
    echo -e "  ${GREEN}✓${NC} Campaign status: ${LSTATUS}"

    sleep 3

    # ── 6. Show Stats ────────────────────────────────────────
    echo -e "\n${BLUE}▶ Campaign Stats:${NC}"
    STATS=$(curl -s "${BASE_URL}/api/attack/stats/${CAMP_ID}" 2>/dev/null)
    echo "$STATS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
t = d.get('totals', {})
print(f'  Targets:    {t.get(\"targets\",0)}')
print(f'  Sent:       {t.get(\"sent\",0)}')
print(f'  Failed:     {t.get(\"failed\",0)}')
print(f'  Clicked:    {t.get(\"clicked\",0)}')
print(f'  Submitted:  {t.get(\"submitted\",0)}')
" 2>/dev/null
else
    echo -e "  ${YELLOW}ℹ${NC} No campaign created (OSINT scan may not have found target emails)"
fi

echo -e "\n${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  ${GREEN}✓ OSINT → Campaign demo complete!${NC}"
echo -e "  ${BLUE}Dashboard: ${BASE_URL}/attack/${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
