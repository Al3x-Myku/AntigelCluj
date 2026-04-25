import requests
import time
import random
import sys
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
            status = "🔴 ANOMALY" if data.get("is_anomalous") else "🟢 NORMAL "
            print(f"[{time.strftime('%H:%M:%S')}] {status} | Score: {score:.2f} | User: {data.get('username')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed to connect to server: {e}")

def run_demo(base_url, attack_ratio, min_sleep, max_sleep):
    print("🚀 PhishGuard Traffic Simulator Started")
    print(f"Targeting: {base_url}")
    print(f"Attack Ratio: {attack_ratio*100:.1f}% | Interval: {min_sleep}-{max_sleep}s")
    print("Pumping live events into the Defense Monitor...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            is_attack = random.random() < attack_ratio
            simulate_login(base_url, is_attack=is_attack)
            time.sleep(random.uniform(min_sleep, max_sleep))
    except KeyboardInterrupt:
        print("\nStopping demo traffic.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate traffic for PhishGuard.")
    parser.add_argument("--url", default=os.getenv("BASE_URL", "http://localhost:8000"), help="Base URL of the backend server")
    parser.add_argument("--attack-ratio", type=float, default=0.2, help="Probability of an attack (0.0 to 1.0)")
    parser.add_argument("--min-sleep", type=float, default=2.0, help="Minimum sleep between requests")
    parser.add_argument("--max-sleep", type=float, default=5.0, help="Maximum sleep between requests")
    parser.add_argument("--attack-only", action="store_true", help="Send a single attack event and exit")
    
    args = parser.parse_args()

    if args.attack_only:
        simulate_login(args.url, is_attack=True)
    else:
        run_demo(args.url, args.attack_ratio, args.min_sleep, args.max_sleep)
