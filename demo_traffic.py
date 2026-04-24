import requests
import time
import random
import sys

BASE_URL = "http://localhost:8000"

def simulate_login(is_attack=False):
    """Hits the simulation endpoint to inject real-time events."""
    endpoint = f"{BASE_URL}/api/defense/simulate-login"
    if is_attack:
        endpoint += "?is_attack=true"
    
    try:
        response = requests.post(endpoint)
        if response.status_code == 200:
            data = response.json()
            score = data.get("anomaly_score", 0)
            status = "🔴 ANOMALY" if data.get("is_anomalous") else "🟢 NORMAL "
            print(f"[{time.strftime('%H:%M:%S')}] {status} | Score: {score:.2f} | User: {data.get('username')}")
        else:
            print(f"Error: {response.status_code}")
    except Exception as e:
        print(f"Failed to connect to server: {e}")

def run_demo():
    print("🚀 PhishGuard Traffic Simulator Started")
    print("Pumping live events into the Defense Monitor...")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            # Randomly decide between normal and attack traffic
            # 80% normal, 20% suspicious/attack
            roll = random.random()
            if roll < 0.8:
                simulate_login(is_attack=False)
            else:
                simulate_login(is_attack=True)
                
            # Wait between 2 and 5 seconds for the next event
            time.sleep(random.uniform(2, 5))
    except KeyboardInterrupt:
        print("\nStopping demo traffic.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--attack":
        simulate_login(is_attack=True)
    else:
        run_demo()
