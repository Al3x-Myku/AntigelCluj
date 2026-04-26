#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# PhishGuard — Detection Accuracy Benchmark
# ═══════════════════════════════════════════════════════════════
# Measures the anomaly detection system's effectiveness:
#   1. Trains the model
#   2. Sends N normal + M attack login events
#   3. Computes TPR, FPR, Accuracy, Precision, F1
#   4. Displays formatted results

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

BASE_URL="${BASE_URL:-http://localhost:8000}"
NORMAL_COUNT="${1:-50}"
ATTACK_COUNT="${2:-20}"

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  📊 Detection Accuracy Benchmark${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "  Normal Events: ${BOLD}${NORMAL_COUNT}${NC}"
echo -e "  Attack Events: ${BOLD}${ATTACK_COUNT}${NC}"
echo ""

# ── Health Check ─────────────────────────────────────────────
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health" 2>/dev/null || echo "000")
if [ "$HEALTH" != "200" ]; then
    echo -e "${RED}✗ Server not reachable at ${BASE_URL}${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Server is running"

# ── Train Model ──────────────────────────────────────────────
echo -e "\n${BLUE}▶ Training anomaly detection model...${NC}"
TRAIN=$(curl -s -X POST "${BASE_URL}/api/defense/train" 2>/dev/null)
echo -e "${GREEN}✓${NC} Model trained"

# ── Send Normal Events ───────────────────────────────────────
echo -e "\n${BLUE}▶ Sending ${NORMAL_COUNT} normal login events...${NC}"
NORMAL_DETECTED=0
for i in $(seq 1 $NORMAL_COUNT); do
    RESULT=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login" 2>/dev/null)
    IS_ANOM=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_anomalous',False))" 2>/dev/null || echo "False")
    if [ "$IS_ANOM" = "True" ]; then
        NORMAL_DETECTED=$((NORMAL_DETECTED+1))
    fi
    # Progress indicator
    if [ $((i % 10)) -eq 0 ]; then echo -n "."; fi
done
echo ""
echo -e "${GREEN}✓${NC} Done. False positives: ${NORMAL_DETECTED}/${NORMAL_COUNT}"

# ── Send Attack Events ───────────────────────────────────────
echo -e "\n${BLUE}▶ Sending ${ATTACK_COUNT} attack login events...${NC}"
ATTACK_DETECTED=0
BANS_TRIGGERED=0
LOCKDOWNS=0
for i in $(seq 1 $ATTACK_COUNT); do
    RESULT=$(curl -s -X POST "${BASE_URL}/api/defense/simulate-login?is_attack=true" 2>/dev/null)
    IS_ANOM=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('is_anomalous',False))" 2>/dev/null || echo "False")
    HAS_BAN=$(echo "$RESULT" | python3 -c "import sys,json; print('ban_triggered' in json.load(sys.stdin))" 2>/dev/null || echo "False")
    HAS_LOCK=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('auto_lockdown_triggered',False))" 2>/dev/null || echo "False")
    if [ "$IS_ANOM" = "True" ]; then ATTACK_DETECTED=$((ATTACK_DETECTED+1)); fi
    if [ "$HAS_BAN" = "True" ]; then BANS_TRIGGERED=$((BANS_TRIGGERED+1)); fi
    if [ "$HAS_LOCK" = "True" ]; then LOCKDOWNS=$((LOCKDOWNS+1)); fi
    if [ $((i % 10)) -eq 0 ]; then echo -n "."; fi
done
echo ""
echo -e "${GREEN}✓${NC} Done. True positives: ${ATTACK_DETECTED}/${ATTACK_COUNT}"

# ── Compute Metrics ──────────────────────────────────────────
TP=$ATTACK_DETECTED
FP=$NORMAL_DETECTED
TN=$((NORMAL_COUNT - NORMAL_DETECTED))
FN=$((ATTACK_COUNT - ATTACK_DETECTED))
TOTAL=$((NORMAL_COUNT + ATTACK_COUNT))

# Use python for float math
METRICS=$(python3 -c "
tp, fp, tn, fn = $TP, $FP, $TN, $FN
total = tp + fp + tn + fn
tpr = tp / max(tp + fn, 1) * 100
fpr = fp / max(fp + tn, 1) * 100
accuracy = (tp + tn) / max(total, 1) * 100
precision = tp / max(tp + fp, 1) * 100
recall = tpr
f1 = 2 * (precision * recall) / max(precision + recall, 0.01)
print(f'{tpr:.1f}|{fpr:.1f}|{accuracy:.1f}|{precision:.1f}|{f1:.1f}')
" 2>/dev/null)

TPR=$(echo "$METRICS" | cut -d'|' -f1)
FPR=$(echo "$METRICS" | cut -d'|' -f2)
ACC=$(echo "$METRICS" | cut -d'|' -f3)
PREC=$(echo "$METRICS" | cut -d'|' -f4)
F1=$(echo "$METRICS" | cut -d'|' -f5)

# ── Results ──────────────────────────────────────────────────
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  DETECTION BENCHMARK RESULTS${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Confusion Matrix${NC}"
echo -e "  ┌──────────────┬────────────────┬────────────────┐"
echo -e "  │              │ ${BOLD}Pred: Normal${NC}  │ ${BOLD}Pred: Anomaly${NC} │"
echo -e "  ├──────────────┼────────────────┼────────────────┤"
printf "  │ ${BOLD}Act: Normal${NC}  │ TN: %-10s │ FP: %-10s │\n" "$TN" "$FP"
printf "  │ ${BOLD}Act: Attack${NC}  │ FN: %-10s │ TP: %-10s │\n" "$FN" "$TP"
echo -e "  └──────────────┴────────────────┴────────────────┘"
echo ""
echo -e "  ${BOLD}Performance Metrics${NC}"
echo -e "  ────────────────────────────────────"
echo -e "  Detection Rate (TPR):   ${BOLD}${GREEN}${TPR}%${NC}"
echo -e "  False Alarm Rate (FPR): ${BOLD}${YELLOW}${FPR}%${NC}"
echo -e "  Accuracy:               ${BOLD}${ACC}%${NC}"
echo -e "  Precision:              ${BOLD}${PREC}%${NC}"
echo -e "  F1 Score:               ${BOLD}${GREEN}${F1}%${NC}"
echo ""
echo -e "  ${BOLD}Response Actions${NC}"
echo -e "  ────────────────────────────────────"
echo -e "  IP Bans Triggered:      ${BOLD}${BANS_TRIGGERED}${NC}"
echo -e "  Auto-Lockdowns:         ${BOLD}${LOCKDOWNS}${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"

# Grade
TPR_NUM=$(echo "$TPR" | cut -d'.' -f1)
if [ "$TPR_NUM" -ge 90 ] 2>/dev/null; then
    echo -e "  Grade: ${GREEN}${BOLD}A — Excellent Detection${NC}"
elif [ "$TPR_NUM" -ge 75 ] 2>/dev/null; then
    echo -e "  Grade: ${YELLOW}${BOLD}B — Good Detection${NC}"
elif [ "$TPR_NUM" -ge 50 ] 2>/dev/null; then
    echo -e "  Grade: ${YELLOW}${BOLD}C — Moderate Detection${NC}"
else
    echo -e "  Grade: ${RED}${BOLD}D — Needs Improvement${NC}"
fi

echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
