"""Seed script — populate DB with fake accounts, login events, and demo data."""

import os
import sys
import random
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faker import Faker
from backend.database import SessionLocal, init_db
from backend.models.account import Account, Card, Session, Subscription, ApiToken
from backend.models.login_event import LoginEvent

fake = Faker()
Faker.seed(42)
random.seed(42)

VICTIM_PC1_IP = os.getenv("VICTIM_PC1_IP", "192.168.1.101")
VICTIM_PC2_IP = os.getenv("VICTIM_PC2_IP", "192.168.1.102")


def seed_accounts(db):
    """Create 10 demo accounts with resources."""
    accounts = []
    plans = ["Basic Plan", "Pro Plan", "Enterprise Plan", "Student Plan"]
    card_types = ["visa", "mastercard"]
    usual_ips = [
        VICTIM_PC1_IP, VICTIM_PC2_IP,
        "192.168.1.10", "192.168.1.11", "192.168.1.12",
        "192.168.1.13", "192.168.1.14", "192.168.1.15",
        "192.168.1.16", "192.168.1.17",
    ]

    for i in range(10):
        acct = Account(
            username=fake.user_name() if i >= 2 else f"victim{i + 1}",
            email=fake.email() if i >= 2 else f"victim{i + 1}@phishguard.local",
            full_name=fake.name(),
            is_active=True,
            usual_ip=usual_ips[i],
            usual_city="Cluj-Napoca",
            usual_country="Romania",
        )
        db.add(acct)
        db.flush()

        # 2 cards per account
        for j in range(2):
            card = Card(
                account_id=acct.id,
                card_number_masked=f"**** **** **** {random.randint(1000, 9999)}",
                card_type=random.choice(card_types),
                status="active",
            )
            db.add(card)

        # 1–3 sessions
        for j in range(random.randint(1, 3)):
            sess = Session(
                account_id=acct.id,
                ip_address=usual_ips[i],
                user_agent=fake.user_agent(),
                status="active",
            )
            db.add(sess)

        # 1 subscription
        sub = Subscription(
            account_id=acct.id,
            plan_name=random.choice(plans),
            status="active",
        )
        db.add(sub)

        # 2 API tokens
        for j in range(2):
            token = ApiToken(
                account_id=acct.id,
                token_name=f"{'mobile' if j == 0 else 'desktop'}-app-key",
                status="active",
            )
            db.add(token)

        accounts.append(acct)

    db.commit()
    print(f"✓ Created {len(accounts)} accounts with resources")
    return accounts


def seed_login_events(db, accounts):
    """Generate ~500 normal login events for MCD training + 30 anomalous ones."""
    now = datetime.utcnow()
    events = []

    # --- Normal events (500) ---
    for _ in range(500):
        acct = random.choice(accounts)
        day_offset = random.randint(1, 90)
        hour = random.gauss(12, 3)  # Peak around noon
        hour = max(6, min(20, hour))  # Clamp to 6–20
        day_of_week = random.randint(0, 4)  # Mon–Fri mostly

        evt = LoginEvent(
            account_id=acct.id,
            username=acct.username,
            ip_address=acct.usual_ip,
            timestamp=now - timedelta(days=day_offset, hours=random.randint(0, 23)),
            success=True,
            hour_of_day=round(hour, 2),
            day_of_week=float(day_of_week),
            login_failures_last_hour=float(random.choices([0, 0, 0, 0, 1], weights=[80, 5, 5, 5, 5])[0]),
            ip_is_new=0.0,
            device_is_new=0.0,
            geo_distance_km=round(random.uniform(0, 10), 2),
            time_since_last_login_hrs=round(random.uniform(1, 24), 2),
            typing_speed_ms=round(random.gauss(100, 15), 2),
            anomaly_score=None,
            is_anomalous=False,
            device_fingerprint=f"dev-{acct.id}-main",
            country="Romania",
            city="Cluj-Napoca",
        )
        events.append(evt)

    # --- Anomalous events (30) ---
    attacker_ips = ["45.33.32.156", "185.220.101.1", "91.219.237.42", "23.129.64.100"]
    attacker_cities = [("Moscow", "Russia"), ("Beijing", "China"), ("Lagos", "Nigeria"), ("Karachi", "Pakistan")]

    for _ in range(30):
        acct = random.choice(accounts[:2])  # Target victim1/victim2
        city, country = random.choice(attacker_cities)

        evt = LoginEvent(
            account_id=acct.id,
            username=acct.username,
            ip_address=random.choice(attacker_ips),
            timestamp=now - timedelta(days=random.randint(0, 5), hours=random.randint(0, 5)),
            success=random.choice([True, False]),
            hour_of_day=round(random.uniform(1, 5), 2),  # Middle of night
            day_of_week=float(random.randint(5, 6)),  # Weekend
            login_failures_last_hour=float(random.randint(3, 10)),
            ip_is_new=1.0,
            device_is_new=1.0,
            geo_distance_km=round(random.uniform(500, 5000), 2),
            time_since_last_login_hrs=round(random.uniform(0.01, 0.5), 4),
            typing_speed_ms=round(random.uniform(10, 30), 2),  # Bot-like speed
            anomaly_score=None,
            is_anomalous=False,  # Will be scored by detector
            device_fingerprint=f"unknown-{random.randint(1000, 9999)}",
            country=country,
            city=city,
        )
        events.append(evt)

    db.add_all(events)
    db.commit()
    print(f"✓ Created {len(events)} login events (500 normal + 30 anomalous)")


def run_seed():
    """Main seed entry point."""
    from dotenv import load_dotenv
    load_dotenv()

    init_db()
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(Account).count()
        if existing > 0:
            print(f"⚠ Database already has {existing} accounts. Skipping seed.")
            print("  Delete phishguard.db and re-run to re-seed.")
            return

        accounts = seed_accounts(db)
        seed_login_events(db, accounts)
        print("\n✅ Seed complete!")
        print(f"   Victim 1: victim1 ({VICTIM_PC1_IP})")
        print(f"   Victim 2: victim2 ({VICTIM_PC2_IP})")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
