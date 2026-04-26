import requests
import time
import random
import sys
import json
import argparse
import os

def simulate_login(base_url, is_attack=False):
    """Hits the simulation endpoint to inject real-time events."""
    endpoint = f"{base_url}/api/defense/simulate-login"
    params = {'is_attack': 'true'} if is_attack else {}
    
    try:
        response = requests.post(endpoint, params=params)
        if response.status_code == 200:
            data = response.json()
            score = data.get("anomaly_score", 0)
            is_anom = data.get("is_anomalous", False)
            status = "🔴 ANOMALY" if is_anom else "🟢 NORMAL "
            print(f"[{time.strftime('%H:%M:%S')}] {status} | Score: {score:.2f} | User: {data.get('username')}")
            return {
                "score": score,
                "is_anomalous": is_anom,
                "was_attack": is_attack,
                "username": data.get("username"),
                "ban_triggered": data.get("ban_triggered"),
                "auto_lockdown_triggered": data.get("auto_lockdown_triggered", False),
            }
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Failed to connect to server: {e}")
        return None

def run_demo(base_url, attack_ratio, min_sleep, max_sleep, count=0):
    """Run the demo traffic generator.
    
    Args:
        count: If > 0, run exactly this many events then stop. If 0, run forever.
    """
    print("🚀 PhishGuard Traffic Simulator Started")
    print(f"Targeting: {base_url}")
    print(f"Attack Ratio: {attack_ratio*100:.1f}% | Interval: {min_sleep}-{max_sleep}s")
    if count > 0:
        print(f"Running {count} events...")
    else:
        print("Pumping live events into the Defense Monitor...")
        print("Press Ctrl+C to stop.\n")
    
    results = []
    i = 0
    
    try:
        while True:
            if count > 0 and i >= count:
                break
            is_attack = random.random() < attack_ratio
            result = simulate_login(base_url, is_attack=is_attack)
            if result:
                results.append(result)
            i += 1
            if count > 0 and i >= count:
                break
            time.sleep(random.uniform(min_sleep, max_sleep))
    except KeyboardInterrupt:
        print("\nStopping demo traffic.")
    
    return results

def print_summary(results):
    """Print a summary of the simulation results."""
    if not results:
        print("\nNo results to summarize.")
        return
    
    total = len(results)
    attacks_sent = sum(1 for r in results if r["was_attack"])
    normals_sent = total - attacks_sent
    true_pos = sum(1 for r in results if r["was_attack"] and r["is_anomalous"])
    false_pos = sum(1 for r in results if not r["was_attack"] and r["is_anomalous"])
    true_neg = sum(1 for r in results if not r["was_attack"] and not r["is_anomalous"])
    false_neg = sum(1 for r in results if r["was_attack"] and not r["is_anomalous"])
    bans = sum(1 for r in results if r.get("ban_triggered"))
    lockdowns = sum(1 for r in results if r.get("auto_lockdown_triggered"))
    
    tpr = true_pos / max(attacks_sent, 1) * 100
    fpr = false_pos / max(normals_sent, 1) * 100
    accuracy = (true_pos + true_neg) / max(total, 1) * 100
    precision = true_pos / max(true_pos + false_pos, 1) * 100
    recall = tpr
    f1 = 2 * (precision * recall) / max(precision + recall, 0.01)
    
    print("\n" + "═" * 60)
    print("📊 SIMULATION RESULTS")
    print("═" * 60)
    print(f"  Total Events:     {total}")
    print(f"  Attacks Sent:     {attacks_sent}")
    print(f"  Normal Sent:      {normals_sent}")
    print(f"  ───────────────────────────────")
    print(f"  True Positives:   {true_pos}  (attacks detected)")
    print(f"  False Positives:  {false_pos}  (normals flagged)")
    print(f"  True Negatives:   {true_neg}  (normals passed)")
    print(f"  False Negatives:  {false_neg}  (attacks missed)")
    print(f"  ───────────────────────────────")
    print(f"  Detection Rate:   {tpr:.1f}%  (TPR/Sensitivity)")
    print(f"  False Alarm Rate: {fpr:.1f}%  (FPR)")
    print(f"  Accuracy:         {accuracy:.1f}%")
    print(f"  Precision:        {precision:.1f}%")
    print(f"  F1 Score:         {f1:.1f}%")
    print(f"  ───────────────────────────────")
    print(f"  Bans Triggered:   {bans}")
    print(f"  Auto-Lockdowns:   {lockdowns}")
    print("═" * 60)
    
    return {
        "total": total,
        "attacks_sent": attacks_sent,
        "normals_sent": normals_sent,
        "true_positives": true_pos,
        "false_positives": false_pos,
        "true_negatives": true_neg,
        "false_negatives": false_neg,
        "tpr": round(tpr, 2),
        "fpr": round(fpr, 2),
        "accuracy": round(accuracy, 2),
        "precision": round(precision, 2),
        "f1": round(f1, 2),
        "bans": bans,
        "lockdowns": lockdowns,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate traffic for PhishGuard.")
    parser.add_argument("--url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="Base URL of the backend server")
    parser.add_argument("--attack-ratio", type=float, default=0.2, help="Probability of an attack (0.0 to 1.0)")
    parser.add_argument("--min-sleep", type=float, default=2.0, help="Minimum sleep between requests")
    parser.add_argument("--max-sleep", type=float, default=5.0, help="Maximum sleep between requests")
    parser.add_argument("--attack-only", action="store_true", help="Send a single attack event and exit")
    parser.add_argument("--count", type=int, default=0, help="Run exactly N events then stop (0 = infinite)")
    parser.add_argument("--json-report", action="store_true", help="Output machine-readable JSON summary")
    parser.add_argument("--fast", action="store_true", help="Minimal delay between events (0.1-0.3s)")
    
    args = parser.parse_args()

    if args.fast:
        args.min_sleep = 0.1
        args.max_sleep = 0.3

    if args.attack_only:
        simulate_login(args.url, is_attack=True)
    else:
        results = run_demo(args.url, args.attack_ratio, args.min_sleep, args.max_sleep, count=args.count)
        stats = print_summary(results)
        
        if args.json_report and stats:
            print("\n--- JSON_REPORT_START ---")
            print(json.dumps(stats, indent=2))
            print("--- JSON_REPORT_END ---")
