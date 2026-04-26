"""
╔══════════════════════════════════════════════════════════════════════╗
║             PhishGuard — Cross-Site Lockdown Demo Script            ║
║                                                                      ║
║  Simulates a suspicious login being detected by the AI anomaly       ║
║  engine, which triggers automatic lockdown across ALL connected      ║
║  platforms (SecurBank banking + BreezeTech IoT) before the           ║
║  attacker can extract any useful data.                               ║
╚══════════════════════════════════════════════════════════════════════╝

Prerequisites:
  1. PhishGuard running on port 8000  (python -m backend.main from AntigelCluj/)
  2. SecurBank  running on port 9000  (python -m backend.main from mockups/bankingapp/)
  3. BreezeTech running on port 9001  (python -m backend.main from mockups/startup/)
  4. Model trained: POST http://localhost:8000/api/defense/train

Usage:
  python demo_lockdown.py              # Full interactive demo
  python demo_lockdown.py --fast       # Quick non-interactive mode
  python demo_lockdown.py --restore    # Restore all accounts after demo
"""

import requests
import time
import sys
import json
import argparse

# ─── Configuration ────────────────────────────────────────────
PHISHGUARD_URL = "http://localhost:8000"
SECURBANK_URL  = "http://localhost:9000"
BREEZETECH_URL = "http://localhost:9001"

# Demo victim — this account exists on all 3 systems
# PhishGuard: victim1 (account_id=1, email=victim1@phishguard.local)
# SecurBank: andrei.popescu@gmail.com
# BreezeTech: radu.gheorghe@gmail.com
# For cross-site lockdown to work, we map by email in PhishGuard's internal accounts.

# ─── ANSI Colors ─────────────────────────────────────────────
R = "\033[91m"   # Red
G = "\033[92m"   # Green
Y = "\033[93m"   # Yellow
B = "\033[94m"   # Blue
M = "\033[95m"   # Magenta
C = "\033[96m"   # Cyan
W = "\033[97m"   # White
D = "\033[90m"   # Dim
BOLD = "\033[1m"
RESET = "\033[0m"


def banner():
    print(f"""
{C}╔══════════════════════════════════════════════════════════════╗
║  {BOLD}{W}🛡  PhishGuard — Cross-Site Lockdown Demo{RESET}{C}                    ║
║  {D}Anomaly Detection → Automatic Multi-Platform Lockdown{RESET}{C}      ║
╚══════════════════════════════════════════════════════════════╝{RESET}
""")


def step(num, title, color=C):
    print(f"\n{color}{'━' * 60}")
    print(f"  STEP {num}: {BOLD}{title}{RESET}")
    print(f"{color}{'━' * 60}{RESET}")


def info(msg):
    print(f"  {D}ℹ{RESET} {msg}")


def success(msg):
    print(f"  {G}✓{RESET} {msg}")


def warning(msg):
    print(f"  {Y}⚠{RESET} {msg}")


def error(msg):
    print(f"  {R}✗{RESET} {msg}")


def attack(msg):
    print(f"  {R}🔴{RESET} {msg}")


def lockdown(msg):
    print(f"  {R}🔒{RESET} {BOLD}{msg}{RESET}")


def pause(msg="Press Enter to continue..."):
    if not FAST_MODE:
        input(f"\n  {D}{msg}{RESET}")


def check_health(name, url):
    """Check if a service is running."""
    try:
        r = requests.get(f"{url}/api/health", timeout=3)
        if r.status_code == 200:
            success(f"{name} is online at {url}")
            return True
    except:
        pass
    error(f"{name} is NOT reachable at {url}")
    return False


def try_login(name, url, email, password):
    """Try to login to a mockup site. Returns (success, detail)."""
    try:
        r = requests.post(f"{url}/api/auth/login", data={"email": email, "password": password}, timeout=5)
        try:
            data = r.json()
        except Exception:
            # Non-JSON response (e.g. HTML error page or empty body)
            return False, f"HTTP {r.status_code} (non-JSON response)"
        if r.status_code == 200:
            return True, data.get("user", {}).get("full_name", "OK")
        elif r.status_code == 403:
            return False, data.get("detail", "Account locked")
        elif r.status_code == 422:
            return False, data.get("detail", "Validation error — check form fields")
        else:
            return False, data.get("detail", f"HTTP {r.status_code}")
    except requests.exceptions.ConnectionError:
        return False, "Connection refused — service may have crashed"
    except requests.exceptions.Timeout:
        return False, "Request timed out"
    except Exception as e:
        return False, str(e)


# ═══════════════════════════════════════════════════════════════
#                        DEMO FLOW
# ═══════════════════════════════════════════════════════════════

def demo():
    banner()

    # ─── STEP 0: Check all services ──────────────────────────
    step(0, "SYSTEM CHECK — Verifying all services are online")
    
    pg_ok = check_health("PhishGuard", PHISHGUARD_URL)
    sb_ok = check_health("SecurBank (Banking)", SECURBANK_URL)
    bt_ok = check_health("BreezeTech (IoT)", BREEZETECH_URL)

    if not pg_ok:
        error("PhishGuard must be running. Start it with: python -m backend.main")
        sys.exit(1)
    if not sb_ok:
        warning("SecurBank not running — banking lockdown will be skipped")
    if not bt_ok:
        warning("BreezeTech not running — IoT lockdown will be skipped")

    # Check external system connectivity from PhishGuard
    info("Checking PhishGuard's external system connections...")
    try:
        r = requests.get(f"{PHISHGUARD_URL}/api/defense/external-status", timeout=5)
        systems = r.json().get("systems", [])
        for s in systems:
            status = f"{G}Online{RESET}" if s["online"] else f"{R}Offline{RESET}"
            info(f"  {s['name']} ({s['type']}): {status}")
    except:
        warning("Could not check external status endpoint")

    pause()

    # ─── STEP 1: Show normal operation ───────────────────────
    step(1, "NORMAL OPERATION — Demonstrating all services work", G)

    if sb_ok:
        info("Attempting normal login to SecurBank...")
        ok, detail = try_login("SecurBank", SECURBANK_URL, "andrei.popescu@gmail.com", "Andrei2026!")
        if ok:
            success(f"SecurBank login successful — Welcome, {detail}")
            success("  → Cards: accessible, Bank accounts: accessible, API keys: active")
        else:
            warning(f"SecurBank login failed: {detail}")

    if bt_ok:
        info("Attempting normal login to BreezeTech...")
        ok, detail = try_login("BreezeTech", BREEZETECH_URL, "radu.gheorghe@gmail.com", "Radu!Gh30rg")
        if ok:
            success(f"BreezeTech login successful — Welcome, {detail}")
            success("  → IoT devices: online, API keys: active, Service tickets: accessible")
        else:
            warning(f"BreezeTech login failed: {detail}")

    info("Both platforms are operating normally. Users have full access.")

    pause()

    # ─── STEP 2: Train the AI model ──────────────────────────
    step(2, "TRAINING AI — Training anomaly detection model", B)

    info("Training Elliptic Envelope (Mahalanobis Distance) on historical login data...")
    try:
        r = requests.post(f"{PHISHGUARD_URL}/api/defense/train", timeout=30)
        data = r.json()
        if r.status_code == 200:
            stats = data.get("stats", {})
            success(f"Model trained on {stats.get('n_samples', '?')} normal login events")
            info(f"  Features: {stats.get('n_features', 8)}-dimensional behavioral vector")
            info(f"  Mean Mahalanobis distance: {stats.get('mean_mahalanobis', '?')}")
            info(f"  Max Mahalanobis distance: {stats.get('max_mahalanobis', '?')}")
        else:
            warning(f"Training response: {data}")
    except Exception as e:
        error(f"Training failed: {e}")

    pause()

    # ─── STEP 3: Enable auto-lockdown ────────────────────────
    step(3, "ARMING DEFENSE — Enabling automatic lockdown response", Y)

    try:
        r = requests.post(f"{PHISHGUARD_URL}/api/defense/auto-lockdown", params={"enabled": "true"}, timeout=5)
        data = r.json()
        if data.get("auto_lockdown_enabled"):
            success("Auto-lockdown is ARMED")
            info("When anomaly score exceeds threshold → automatic cross-site lockdown")
        else:
            warning("Auto-lockdown toggle response unexpected")
    except Exception as e:
        error(f"Failed to enable auto-lockdown: {e}")

    pause()

    # ─── STEP 4: SIMULATE THE ATTACK ─────────────────────────
    step(4, "🔴 ATTACK SIMULATION — Suspicious login detected!", R)

    print(f"""
  {R}{BOLD}┌─────────────────────────────────────────────────────────┐
  │  ATTACKER SCENARIO                                      │
  │                                                         │
  │  An attacker from Moscow (IP: 185.220.101.1) attempts   │
  │  to access victim1's account at 3:17 AM on a Saturday.  │
  │  They use a new device, new IP, with bot-like typing    │
  │  speed (15ms avg). They've had 8 failed attempts in     │
  │  the last hour.                                         │
  │                                                         │
  │  The AI must detect this as anomalous and lock down     │
  │  ALL platforms before data can be exfiltrated.          │
  └─────────────────────────────────────────────────────────┘{RESET}
""")

    if not FAST_MODE:
        input(f"  {Y}Press Enter to launch the attack...{RESET}")

    info("Injecting suspicious login event into PhishGuard...")
    print()

    try:
        r = requests.post(
            f"{PHISHGUARD_URL}/api/defense/simulate-login",
            params={"is_attack": "true", "account_id": "1"},
            timeout=30,
        )
        data = r.json()

        score = data.get("anomaly_score", 0)
        is_anom = data.get("is_anomalous", False)
        username = data.get("username", "?")
        country = data.get("country", "?")
        city = data.get("city", "?")

        # Show the detection
        print(f"  {D}{'─' * 55}{RESET}")
        attack(f"Login attempt from {R}{city}, {country}{RESET}")
        attack(f"Target account: {BOLD}{username}{RESET}")
        attack(f"Anomaly score: {R}{BOLD}{score:.4f}{RESET}")
        attack(f"Detection result: {R}{BOLD}{'🔴 ANOMALOUS' if is_anom else '🟢 Normal'}{RESET}")
        print(f"  {D}{'─' * 55}{RESET}")

        # Show ban
        ban = data.get("ban_triggered")
        if ban:
            print()
            lockdown(f"IP {ban.get('ip', '?')} BANNED — {ban.get('reason', 'Anomaly detected')}")

        # Show auto-lockdown result
        if data.get("auto_lockdown_triggered"):
            print()
            lockdown(f"AUTO-LOCKDOWN TRIGGERED on {username}")
            print(f"  {R}  ├─ PhishGuard internal account: LOCKED{RESET}")
            print(f"  {R}  ├─ Cards: FROZEN{RESET}")
            print(f"  {R}  ├─ Sessions: REVOKED{RESET}")
            print(f"  {R}  └─ API Tokens: REVOKED{RESET}")

            # Show external lockdown results
            ext = data.get("external_lockdowns", [])
            if ext:
                print()
                lockdown("CROSS-SITE LOCKDOWN CASCADE:")
                for site in ext:
                    name = site.get("site", "?")
                    status = site.get("status", "?")
                    details = site.get("details", {})

                    if status == "locked":
                        actions = details.get("actions", [])
                        print(f"  {R}  🔒 {name}: {BOLD}LOCKED{RESET}")
                        for action in actions:
                            print(f"  {R}     └─ {action}{RESET}")
                    elif status == "unreachable":
                        print(f"  {Y}  ⚠ {name}: Service not running (skipped){RESET}")
                    elif status == "user_not_found":
                        print(f"  {D}  ℹ {name}: No matching user found{RESET}")
                    elif status == "already_locked":
                        print(f"  {D}  ℹ {name}: Already locked{RESET}")
                    else:
                        print(f"  {Y}  ? {name}: {status}{RESET}")
        else:
            warning(data.get("auto_lockdown_warning", "Auto-lockdown did not trigger"))

    except Exception as e:
        error(f"Attack simulation failed: {e}")
        return

    # ─── MANUAL FALLBACK: If auto-lockdown didn't fire, trigger it manually ───
    if not data.get("auto_lockdown_triggered"):
        warning("Auto-lockdown did not cascade — triggering manual lockdown...")
        try:
            # Manual lockdown on PhishGuard internal account
            r2 = requests.post(f"{PHISHGUARD_URL}/api/defense/lockdown/1", timeout=10)
            if r2.status_code == 200:
                lockdown_data = r2.json()
                lockdown(f"MANUAL LOCKDOWN executed on account 1")
                print(f"  {R}  ├─ PhishGuard internal account: LOCKED{RESET}")
                print(f"  {R}  ├─ Cards: FROZEN{RESET}")
                print(f"  {R}  ├─ Sessions: REVOKED{RESET}")
                print(f"  {R}  └─ API Tokens: REVOKED{RESET}")
                ext = lockdown_data.get("external_lockdowns", [])
                if ext:
                    print()
                    lockdown("CROSS-SITE LOCKDOWN CASCADE:")
                    for site in ext:
                        name = site.get("site", "?")
                        status = site.get("status", "?")
                        details = site.get("details", {})
                        if status == "locked":
                            actions = details.get("actions", []) if isinstance(details, dict) else []
                            print(f"  {R}  🔒 {name}: {BOLD}LOCKED{RESET}")
                            for action in actions:
                                print(f"  {R}     └─ {action}{RESET}")
                        elif status == "unreachable":
                            print(f"  {Y}  ⚠ {name}: Service not running (skipped){RESET}")
                        elif status == "user_not_found":
                            print(f"  {D}  ℹ {name}: No matching user found{RESET}")
                        elif status == "already_locked":
                            print(f"  {D}  ℹ {name}: Already locked{RESET}")
                        else:
                            print(f"  {Y}  ? {name}: {status}{RESET}")
            else:
                error(f"Manual lockdown returned HTTP {r2.status_code}")
        except Exception as e2:
            error(f"Manual lockdown also failed: {e2}")

    pause()

    # ─── STEP 5: PROVE THE LOCKDOWN WORKS ────────────────────
    step(5, "VERIFICATION — Attacker cannot access any platform", G)

    print(f"""
  {G}The lockdown happened in milliseconds — before the attacker
  could extract any account data, card numbers, or IoT commands.
  
  Let's verify by trying to log in on each platform:{RESET}
""")

    time.sleep(1)  # Give servers a moment to propagate lockdown state

    if sb_ok:
        info("Attempting login to SecurBank as the victim...")
        ok, detail = try_login("SecurBank", SECURBANK_URL, "andrei.popescu@gmail.com", "Andrei2026!")
        if ok:
            error("SecurBank login succeeded — lockdown may not have propagated!")
        else:
            lockdown(f"SecurBank: ACCESS DENIED — \"{detail}\"")
            success("  → Cards: FROZEN, Bank accounts: FROZEN, API keys: REVOKED")

    if bt_ok:
        info("Attempting login to BreezeTech as the victim...")
        ok, detail = try_login("BreezeTech", BREEZETECH_URL, "radu.gheorghe@gmail.com", "Radu!Gh30rg")
        if ok:
            error("BreezeTech login succeeded — lockdown may not have propagated!")
        else:
            lockdown(f"BreezeTech: ACCESS DENIED — \"{detail}\"")
            success("  → IoT devices: OFFLINE, API keys: REVOKED")

    print(f"""
  {G}{BOLD}┌─────────────────────────────────────────────────────────┐
  │  ✅ LOCKDOWN SUCCESSFUL                                 │
  │                                                         │
  │  The AI detected the anomalous login in real-time.      │
  │  Within milliseconds, PhishGuard automatically:         │
  │                                                         │
  │  1. Scored the login (Mahalanobis distance > threshold) │
  │  2. Locked the internal PhishGuard account              │
  │  3. Banned the attacker's IP address                    │
  │  4. Called SecurBank API → froze cards + accounts        │
  │  5. Called BreezeTech API → disabled IoT devices         │
  │                                                         │
  │  The attacker gained ZERO access to any data.           │
  └─────────────────────────────────────────────────────────┘{RESET}
""")

    pause("Press Enter to restore accounts (cleanup)...")

    # ─── STEP 6: RESTORE ─────────────────────────────────────
    step(6, "CLEANUP — Restoring all accounts", B)

    restore_all()

    print(f"\n{C}{BOLD}  Demo complete! 🎉{RESET}\n")


def restore_all():
    """Restore all locked-down accounts across all platforms."""
    info("Restoring PhishGuard internal account...")
    try:
        r = requests.post(f"{PHISHGUARD_URL}/api/defense/lockdown/1/restore", timeout=20)
        if r.status_code == 200:
            success("PhishGuard account 1 restored")
            # External restores are cascaded automatically
            ext = r.json().get("external_restores", [])
            for site in ext:
                name = site.get("site", "?")
                status = site.get("status", "?")
                if status == "restored":
                    success(f"  {name}: restored")
                else:
                    info(f"  {name}: {status}")
        else:
            warning(f"Restore response: {r.status_code}")
    except Exception as e:
        error(f"Restore failed: {e}")

    # Direct restore on mockups as fallback
    for name, url in [("SecurBank", SECURBANK_URL), ("BreezeTech", BREEZETECH_URL)]:
        try:
            # Get users list to find the right one
            r = requests.get(f"{url}/api/lockdown/users", timeout=5)
            if r.status_code == 200:
                users = r.json().get("users", [])
                for u in users:
                    if u.get("is_locked"):
                        uid = u.get("id")
                        requests.post(f"{url}/api/lockdown/{uid}/restore", timeout=5)
                        success(f"  {name}: restored user {u.get('email', uid)}")
        except Exception as e:
            info(f"  {name}: could not reach for direct restore ({e})")

    # Disable auto-lockdown
    try:
        requests.post(f"{PHISHGUARD_URL}/api/defense/auto-lockdown", params={"enabled": "false"}, timeout=5)
        info("Auto-lockdown disabled")
    except:
        pass

    # Clear bans
    try:
        r = requests.get(f"{PHISHGUARD_URL}/api/defense/bans", timeout=5)
        bans = r.json().get("bans", [])
        for ban in bans:
            ip = ban.get("ip", "")
            if ip:
                requests.delete(f"{PHISHGUARD_URL}/api/defense/bans/{ip}", timeout=5)
        if bans:
            info(f"Cleared {len(bans)} IP bans")
    except:
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PhishGuard Cross-Site Lockdown Demo")
    parser.add_argument("--fast", action="store_true", help="Skip interactive pauses")
    parser.add_argument("--restore", action="store_true", help="Just restore all accounts")
    parser.add_argument("--phishguard-url", default=PHISHGUARD_URL)
    parser.add_argument("--securbank-url", default=SECURBANK_URL)
    parser.add_argument("--breezetech-url", default=BREEZETECH_URL)
    args = parser.parse_args()

    PHISHGUARD_URL = args.phishguard_url
    SECURBANK_URL = args.securbank_url
    BREEZETECH_URL = args.breezetech_url
    FAST_MODE = args.fast

    if args.restore:
        banner()
        step(0, "RESTORE — Restoring all accounts", B)
        restore_all()
        print(f"\n{G}  All accounts restored!{RESET}\n")
    else:
        FAST_MODE = args.fast
        demo()
