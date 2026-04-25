#!/bin/bash
# PhishGuard — Demo Setup
# Run once before the demo. Resets state and trains the ML model.
# Usage: bash demo/00_setup.sh

set -eo pipefail

R='\033[0;31m'  G='\033[0;32m'  Y='\033[1;33m'
C='\033[0;36m'  B='\033[1m'     D='\033[2m'     N='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"

p()  { printf "${C}[%s]${N} %s\n" "$(date +%H:%M:%S)" "$*"; }
ok() { printf "  ${G}ok${N}  %s\n" "$*"; }
kv() { printf "  ${D}%-30s${N}  %s\n" "$1" "$2"; }
err(){ printf "  ${R}ERR${N} %s\n" "$*" >&2; }
die(){ err "$*"; exit 1; }

j() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)" 2>/dev/null || echo "?"; }

echo ""
echo "${B}PhishGuard — Demo Setup${N}"
echo "${D}Server: ${BASE_URL}${N}"
echo ""

# ── 1. Health ────────────────────────────────────────────────────────
p "Health check"
HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health")
[ "$HTTP" = "200" ] || die "Server not running at ${BASE_URL}. Start it with: python -m backend.main"
ok "HTTP 200"

# ── 2. Restore any locked accounts so demo starts clean ─────────────
p "Resetting account lock state"
ACCS=$(curl -s "${BASE_URL}/api/defense/accounts")
LOCKED_IDS=$(echo "$ACCS" | python3 -c "
import sys,json
accs = json.load(sys.stdin)['accounts']
print(' '.join(str(a['id']) for a in accs if a.get('is_locked')))" 2>/dev/null || echo "")
if [ -n "$LOCKED_IDS" ]; then
    for aid in $LOCKED_IDS; do
        curl -s -X POST "${BASE_URL}/api/defense/lockdown/${aid}/restore" > /dev/null
        ok "Account ${aid} restored"
    done
else
    ok "No locked accounts"
fi

# ── 3. Train the anomaly model ───────────────────────────────────────
p "Training anomaly detection model (MinCovDet / Mahalanobis)"
TRAIN=$(curl -s -X POST "${BASE_URL}/api/defense/train")
STATUS=$(echo "$TRAIN" | j "d.get('status','?')")
N_SAMPLES=$(echo "$TRAIN" | j "d.get('stats',{}).get('n_samples','?')")
N_FEAT=$(echo "$TRAIN"   | j "d.get('stats',{}).get('n_features','?')")
MEAN_D=$(echo "$TRAIN"   | j "d.get('stats',{}).get('mean_mahalanobis','?')")
[ "$STATUS" = "trained" ] || die "Train failed: $TRAIN"
ok "$STATUS"
kv "training samples"      "$N_SAMPLES"
kv "feature dimensions"    "$N_FEAT"
kv "mean Mahalanobis dist" "$MEAN_D"

# ── 4. Score historical events ───────────────────────────────────────
p "Scoring all unscored historical events"
SCORE=$(curl -s -X POST "${BASE_URL}/api/defense/score")
SCORED=$(echo "$SCORE" | j "d.get('scored',0)")
ANOM=$(echo "$SCORE"   | j "d.get('anomalies_found',0)")
ok "Done"
kv "events scored"   "$SCORED"
kv "anomalies found" "$ANOM"

# ── 5. Dashboard snapshot ────────────────────────────────────────────
p "Dashboard snapshot"
DASH=$(curl -s "${BASE_URL}/api/defense/dashboard")
kv "total login events"  "$(echo "$DASH" | j "d.get('total_events',0)")"
kv "anomalies flagged"   "$(echo "$DASH" | j "d.get('total_anomalies',0)")"
kv "active accounts"     "$(echo "$DASH" | j "d.get('active_accounts',0)")"
kv "active IP bans"      "$(echo "$DASH" | j "d.get('active_bans',0)")"
kv "threshold (scaled)"  "$(echo "$DASH" | j "d.get('threshold',0)")"

echo ""
echo "${G}${B}Setup complete.${N} Run: ${C}bash demo/01_demo.sh${N}"
echo ""
