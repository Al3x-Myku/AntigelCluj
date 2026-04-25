#!/bin/bash
# PhishGuard — Technical Demo (~60 seconds)
#
# Demonstrates the full attack → detect → respond lifecycle via real API calls.
# Every number shown comes live from the server — nothing is mocked.
#
# Prerequisites: server running, 00_setup.sh already executed.
# Usage:         bash demo/01_demo.sh

set -eo pipefail

R='\033[0;31m'  G='\033[0;32m'  Y='\033[1;33m'
C='\033[0;36m'  B='\033[1m'     D='\033[2m'     N='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"

# Helper: extract JSON field via python3
j() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null || echo "?"; }

# Helpers: print
hdr() { echo ""; echo "${C}${B}── $* ──${N}"; }
p()   { printf "${C}[%s]${N} %s\n" "$(date +%H:%M:%S)" "$*"; }
ok()  { printf "  ${G}✓${N}  %s\n" "$*"; }
row() { printf "  ${D}%-30s${N}  ${B}%s${N}\n" "$1" "$2"; }
err() { printf "  ${R}✗${N}  %s\n" "$*" >&2; }
die() { err "$*"; exit 1; }

PASS=0; FAIL=0
check() {
    local label="$1" actual="$2" expected="$3"
    if [ "$actual" = "$expected" ]; then
        ok "PASS  ${label}: ${actual}"
        PASS=$((PASS+1))
    else
        err "FAIL  ${label}: got '${actual}', want '${expected}'"
        FAIL=$((FAIL+1))
    fi
}

# ════════════════════════════════════════════════════════════════════════
# PREFLIGHT
# ════════════════════════════════════════════════════════════════════════
echo ""
echo "${B}PhishGuard — Technical Demo${N}"
echo "${D}Server: ${BASE_URL}  |  $(date '+%Y-%m-%d %H:%M:%S')${N}"
echo ""

HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health")
[ "$HTTP" = "200" ] || die "Server not reachable (HTTP $HTTP). Run: python -m backend.main"
ok "Server live"

# ════════════════════════════════════════════════════════════════════════
# SECTION 1 — ML ANOMALY DETECTION ENGINE
# ════════════════════════════════════════════════════════════════════════
hdr "1 / 4  Anomaly Detection — MCD + Mahalanobis Distance"

# 1a. Retrain
p "POST /api/defense/train"
TRAIN=$(curl -s -X POST "${BASE_URL}/api/defense/train")
check "status"    "$(echo "$TRAIN" | j "d['status']")"           "trained"
row "samples"     "$(echo "$TRAIN" | j "d['stats']['n_samples']")"
row "features"    "$(echo "$TRAIN" | j "d['stats']['n_features']") dimensions"
row "mean dist"   "$(echo "$TRAIN" | j "d['stats']['mean_mahalanobis']")"
row "max dist"    "$(echo "$TRAIN" | j "d['stats']['max_mahalanobis']")"
echo ""

# 1b. Fire 10 normal logins — all should score low (not anomalous)
p "POST /api/defense/simulate-login  ×10  (normal)"
NORMAL_TP=0
for i in $(seq 1 10); do
    R=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login")
    IS_ANOM=$(echo "$R" | j "d.get('is_anomalous', False)")
    [ "$IS_ANOM" = "True" ] && NORMAL_TP=$((NORMAL_TP+1))
done
FP=$NORMAL_TP
FP_RATE=$(python3 -c "print(f'{$FP/10*100:.0f}%')")
check "false_positive_rate ≤10%"  "$FP_RATE"  "0%"
echo ""

# 1c. Fire 10 attack logins — collect scores and detection
p "POST /api/defense/simulate-login?is_attack=true  ×10  (attack)"
echo ""
echo "  ${D}IP                Country       Score  Detected  Ban${N}"
echo "  ${D}$(printf '─%.0s' {1..58})${N}"
DETECTED=0; BANNED=0
for i in $(seq 1 10); do
    R=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login?is_attack=true")
    IP=$(     echo "$R" | j "d.get('ip_address','?')")
    COUNTRY=$(echo "$R" | j "d.get('country','?')")
    CITY=$(   echo "$R" | j "d.get('city','?')")
    SCORE=$(  echo "$R" | j "f\"{d.get('anomaly_score',0):.4f}\"")
    IS_A=$(   echo "$R" | j "d.get('is_anomalous',False)")
    BAN=$(    echo "$R" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(d['ban_triggered']['type'] if 'ban_triggered' in d else '-')" 2>/dev/null || echo "-")
    DET_ICON="${R}✗${N}"; [ "$IS_A" = "True" ] && { DET_ICON="${G}✓${N}"; DETECTED=$((DETECTED+1)); }
    BAN_ICON="-";         [ "$BAN" != "-" ]    && { BAN_ICON="${R}${BAN}${N}"; BANNED=$((BANNED+1)); }
    printf "  %-20s %-14s %-7s  %b        %b\n" "$IP" "${CITY},${COUNTRY}" "$SCORE" "$DET_ICON" "$BAN_ICON"
    sleep 0.2
done
echo ""
TPR=$(python3 -c "print(f'{$DETECTED/10*100:.0f}%')")
check "detection_rate ≥90%"   "$([ "$DETECTED" -ge 9 ] && echo 'yes' || echo 'no')"  "yes"
row "attacks detected"   "${DETECTED}/10  (${TPR})"
row "bans triggered"     "${BANNED}"
echo ""

# ════════════════════════════════════════════════════════════════════════
# SECTION 2 — EMAIL DEFENSE ENGINE
# ════════════════════════════════════════════════════════════════════════
hdr "2 / 4  Email Defense — Multi-Signal Phishing Classifier"

run_email_scan() {
    local label="$1" subj="$2" body="$3" from="$4"
    p "POST /api/defense/email/scan  — ${label}"
    R=$(curl -s -X POST "${BASE_URL}/api/defense/email/scan" \
        -H "Content-Type: application/json" \
        -d "{\"subject\":\"${subj}\",\"body\":\"${body}\",\"from_addr\":\"${from}\",\"to_addr\":\"victim@company.ro\"}")
    SCORE=$(      echo "$R" | j "d['verdict']['score']")
    RISK=$(       echo "$R" | j "d['verdict']['risk_level']")
    QUARANTINED=$(echo "$R" | j "d['quarantined']")
    FLAGS=$(      echo "$R" | python3 -c "
import sys,json
d=json.load(sys.stdin)
flags=d['verdict']['flags']
for f in flags[:3]: print('      FLAG: '+f[:80])" 2>/dev/null || true)
    row "score"         "$SCORE"
    row "risk_level"    "$RISK"
    row "quarantined"   "$QUARANTINED"
    echo "$FLAGS"
    echo ""
}

run_email_scan \
    "safe email" \
    "Q3 Team Lunch — Friday 12:30" \
    "Hi team, lunch is at noon on Friday at the usual place. See you there." \
    "alice@company.ro"

run_email_scan \
    "credential phish" \
    "URGENT: Your account will be suspended" \
    "Dear user, click http://secure-login.ru/verify?token=xK9zR to verify your bank account immediately or it will be suspended within 24 hours." \
    "noreply@secure-bank-alerts.ru"

run_email_scan \
    "calendar invite phish" \
    "Mandatory: Security Compliance Review" \
    "You have been invited to a mandatory meeting. Join via: https://meet.totally-legit-corp.xyz/join?ref=abc. Attendance is compulsory." \
    "it-security@company-it.com.phish.cc"

# ════════════════════════════════════════════════════════════════════════
# SECTION 3 — PHISHING CAMPAIGN (RED TEAM)
# ════════════════════════════════════════════════════════════════════════
hdr "3 / 4  Red Team — Create, Launch, and Measure Campaign"

# 3a. Create campaign with CSV targets
p "POST /api/attack/campaigns  (Email + Calendar, 3 targets)"
CSV='first_name,last_name,email,phone
Alice,Pop,alice.pop@example.ro,+40721000001
Bob,Ionescu,bob.ionescu@example.ro,+40721000002
Carol,Munteanu,carol.munteanu@example.ro,+40721000003'

CREATE=$(curl -s -X POST "${BASE_URL}/api/attack/campaigns" \
    -F "name=PhishGuard Live Demo" \
    -F "use_email=1" \
    -F "use_calendar=1" \
    -F "email_subject=Action Required: Verify your account immediately" \
    -F "email_body=Dear {{name}}, your account access expires soon. Verify at {{link}} or it will be suspended." \
    -F "calendar_summary=Mandatory: Security Compliance Review" \
    -F "calendar_description=Join the mandatory review at {{link}} to maintain system access." \
    -F "targets_csv=@-;type=text/csv" <<< "$CSV")

CAMP_ID=$(  echo "$CREATE" | j "d['campaign']['id']")
CAMP_STATUS=$(echo "$CREATE" | j "d['campaign']['status']")
TARGETS=$(  echo "$CREATE" | j "d['campaign']['stats']['total_targets']")
CHANNELS=$(  echo "$CREATE" | python3 -c "
import sys,json
d=json.load(sys.stdin)
chs=d['campaign']['channels']
print(', '.join(k for k,v in chs.items() if v))" 2>/dev/null || echo "?")

check "create_status"    "$CAMP_STATUS"   "draft"
check "target_count"     "$TARGETS"       "3"
row "campaign_id"        "$CAMP_ID"
row "channels"           "$CHANNELS"
echo ""

# 3b. Launch
p "POST /api/attack/campaigns/${CAMP_ID}/launch"
LAUNCH=$(curl -s -X POST "${BASE_URL}/api/attack/campaigns/${CAMP_ID}/launch")
L_STATUS=$(echo "$LAUNCH" | j "d['campaign']['status']")
check "launch_status"    "$L_STATUS"   "completed"
echo ""

# 3c. Poll stats
p "GET /api/attack/stats/${CAMP_ID}"
sleep 1
STATS=$(curl -s "${BASE_URL}/api/attack/stats/${CAMP_ID}")
SENT=$(     echo "$STATS" | j "d['totals']['sent']")
FAILED=$(   echo "$STATS" | j "d['totals']['failed']")
CLICKED=$(  echo "$STATS" | j "d['totals']['clicked']")
SUBMITTED=$(echo "$STATS" | j "d['totals']['submitted']")

check "sent_count"       "$SENT"     "3"
check "failed_count"     "$FAILED"   "0"
row "clicked"            "$CLICKED"
row "submitted"          "$SUBMITTED"

# Channel breakdown
echo ""
echo "  ${D}Channel breakdown:${N}"
echo "$STATS" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for ch,v in d['per_channel'].items():
    if v['sent']>0 or v['clicked']>0:
        print(f\"  {'':2}{ch:<12}  sent={v['sent']}  clicked={v['clicked']}  submitted={v['submitted']}\")
" 2>/dev/null || true

# Tracking links
echo ""
p "GET /api/attack/campaigns/${CAMP_ID}  (target tracking tokens)"
DETAIL=$(curl -s "${BASE_URL}/api/attack/campaigns/${CAMP_ID}")
echo "$DETAIL" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for t in d.get('targets',[]):
    tok=t.get('tracking_token','—')
    status=t.get('status','?')
    print(f\"  {t.get('email','?'):<35}  token={tok[:8]}...  status={status}\")
" 2>/dev/null || true
echo ""

# ════════════════════════════════════════════════════════════════════════
# SECTION 4 — ACCOUNT LOCKDOWN
# ════════════════════════════════════════════════════════════════════════
hdr "4 / 4  Account Lockdown — Database-Agnostic Freeze"

# Ensure account 2 is restored first
curl -s -X POST "${BASE_URL}/api/defense/lockdown/2/restore" > /dev/null 2>&1 || true

p "POST /api/defense/lockdown/2"
LK=$(curl -s -X POST "${BASE_URL}/api/defense/lockdown/2")
check "lockdown_result"  "$(echo "$LK" | j "bool(d.get('actions'))")"   "True"
echo ""
row "account_id"         "$(echo "$LK" | j "d['account_id']")"
row "username"           "$(echo "$LK" | j "d['username']")"
row "triggered_by"       "$(echo "$LK" | j "d['triggered_by']")"
row "lockdown_at"        "$(echo "$LK" | j "d['lockdown_at']")"
echo ""
echo "  ${D}Actions executed:${N}"
echo "$LK" | python3 -c "
import sys,json
for a in json.load(sys.stdin).get('actions',[]): print(f'    {a}')
" 2>/dev/null || true
echo ""

# Status tree
p "GET /api/defense/lockdown/2/status"
ST=$(curl -s "${BASE_URL}/api/defense/lockdown/2/status")
check "is_locked"   "$(echo "$ST" | j "str(d.get('is_locked',False))")"   "True"
check "is_active"   "$(echo "$ST" | j "str(d.get('is_active',True))")"    "False"
echo ""

row "username"       "$(echo "$ST" | j "d.get('username','?')")"
row "email"          "$(echo "$ST" | j "d.get('email','?')")"
row "locked_at"      "$(echo "$ST" | j "d.get('locked_at','?')")"

echo ""
echo "  ${D}Resource tree:${N}"
echo "$ST" | python3 -c "
import sys,json
d=json.load(sys.stdin)
cards=d.get('cards',[])
for c in cards:
    print(f\"    card   {c.get('card_number_masked','?'):<25}  type={c.get('card_type','?'):<6}  status={c.get('status','?')}\")
sessions=d.get('sessions',[])
for s in sessions:
    print(f\"    session  id={s.get('session_id',s.get('id','?'))}  active={s.get('is_active','-')}\")
subs=d.get('subscriptions',[])
for s in subs:
    print(f\"    sub    {s.get('plan','?'):<12}  status={s.get('status','?')}\")
tokens=d.get('api_tokens',[])
for t in tokens:
    print(f\"    token  {str(t.get('token','?'))[:12]}...  revoked={t.get('is_revoked','-')}\")
if not cards and not sessions and not subs and not tokens:
    print('    (no additional resources for this account)')
" 2>/dev/null || true
echo ""

# Restore so account is clean after demo
p "POST /api/defense/lockdown/2/restore"
RES=$(curl -s -X POST "${BASE_URL}/api/defense/lockdown/2/restore")
check "restore_status"   "$(echo "$RES" | j "d['status']")"   "restored"
echo ""

# ════════════════════════════════════════════════════════════════════════
# FINAL SCORECARD
# ════════════════════════════════════════════════════════════════════════
hdr "Results"

DASH=$(curl -s "${BASE_URL}/api/defense/dashboard")
EM=$(curl -s "${BASE_URL}/api/defense/email/stats")
BANS=$(curl -s "${BASE_URL}/api/defense/bans")

echo "  ${D}Anomaly engine${N}"
row "  total events in DB"       "$(echo "$DASH" | j "d.get('total_events',0)")"
row "  anomalies flagged"        "$(echo "$DASH" | j "d.get('total_anomalies',0)")"
row "  detection rate (10 bursts)" "${DETECTED}/10 (${TPR})"
row "  false positive rate"      "${FP}/10 (${FP_RATE})"
row "  active IP bans"           "$(echo "$BANS" | j "d.get('total',0)")"
echo ""
echo "  ${D}Email defense${N}"
row "  total emails scanned"     "$(echo "$EM" | j "d.get('total_scanned',0)")"
row "  quarantined"              "$(echo "$EM" | j "d.get('quarantined',0)")"
row "  dangerous"                "$(echo "$EM" | j "d.get('dangerous',0)")"
row "  suspicious"               "$(echo "$EM" | j "d.get('suspicious',0)")"
echo ""
echo "  ${D}Campaign${N}"
row "  campaign id"              "${CAMP_ID}"
row "  targets"                  "3"
row "  sent"                     "${SENT}"
row "  tracking URL pattern"     "${BASE_URL}/phish/{uuid}"
echo ""
echo "  ${D}Self-checks${N}"
echo "  PASS: ${G}${B}${PASS}${N}   FAIL: ${R}${B}${FAIL}${N}"
echo ""
[ "$FAIL" -eq 0 ] && echo "${G}${B}All checks passed.${N}" || echo "${R}${B}${FAIL} check(s) failed — review output above.${N}"
echo ""
