"""Seed script — create 20 demo users with bank accounts, cards, and API keys."""

import os
import sys
import hashlib
import secrets
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from passlib.context import CryptContext
from backend.database import SessionLocal
from backend.models.user import User
from backend.models.bank_account import BankAccount
from backend.models.card import Card
from backend.models.api_key import APIKey

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 20 Demo Users ──────────────────────────────────────────────────────────
DEMO_USERS = [
    {"email": "andrei.popescu@gmail.com",     "password": "Andrei2026!",    "full_name": "Andrei Popescu",      "phone": "+40 721 123 001", "address": "Str. Avram Iancu 14",       "city": "Cluj-Napoca"},
    {"email": "maria.ionescu@yahoo.com",      "password": "Maria#Secure7",  "full_name": "Maria Ionescu",       "phone": "+40 722 234 002", "address": "Bd. Eroilor 22",             "city": "Cluj-Napoca"},
    {"email": "stefan.dumitru@outlook.com",    "password": "St3fan!Pass",    "full_name": "Ștefan Dumitru",      "phone": "+40 723 345 003", "address": "Str. Memorandumului 8",      "city": "Cluj-Napoca"},
    {"email": "elena.popa@gmail.com",         "password": "Elena@2026x",    "full_name": "Elena Popa",          "phone": "+40 724 456 004", "address": "Str. Napoca 31",             "city": "Cluj-Napoca"},
    {"email": "mihai.stan@protonmail.com",    "password": "Mih4i!Bank",     "full_name": "Mihai Stan",          "phone": "+40 725 567 005", "address": "Calea Moților 55",           "city": "Cluj-Napoca"},
    {"email": "ana.radu@gmail.com",           "password": "Ana_Rad!99",     "full_name": "Ana Radu",            "phone": "+40 726 678 006", "address": "Str. Republicii 17",         "city": "Cluj-Napoca"},
    {"email": "cristian.marin@yahoo.com",     "password": "Cristi@n44",     "full_name": "Cristian Marin",      "phone": "+40 727 789 007", "address": "Str. Dorobanților 42",       "city": "Cluj-Napoca"},
    {"email": "diana.voicu@gmail.com",        "password": "Diana!V0icu",    "full_name": "Diana Voicu",         "phone": "+40 728 890 008", "address": "Str. Clinicilor 5",          "city": "Cluj-Napoca"},
    {"email": "bogdan.nagy@outlook.com",      "password": "B0gdan#Nagy",    "full_name": "Bogdan Nagy",         "phone": "+40 729 901 009", "address": "Str. Observatorului 19",     "city": "Cluj-Napoca"},
    {"email": "ioana.moldovan@gmail.com",     "password": "I0ana_Mold!",    "full_name": "Ioana Moldovan",      "phone": "+40 730 012 010", "address": "Aleea Detunata 3",           "city": "Cluj-Napoca"},
    {"email": "adrian.rus@yahoo.com",         "password": "Adri4n#Rus",     "full_name": "Adrian Rus",          "phone": "+40 731 123 011", "address": "Str. Pasteur 60",            "city": "Cluj-Napoca"},
    {"email": "laura.chiriac@gmail.com",      "password": "Laura!Ch1r",     "full_name": "Laura Chiriac",       "phone": "+40 732 234 012", "address": "Str. Piezișă 12",            "city": "Cluj-Napoca"},
    {"email": "razvan.florea@protonmail.com", "password": "R4zvan_Fl!",     "full_name": "Răzvan Florea",       "phone": "+40 733 345 013", "address": "Str. Fabricii 28",           "city": "Cluj-Napoca"},
    {"email": "alexandra.stoica@gmail.com",   "password": "Alex@St01ca",    "full_name": "Alexandra Stoica",    "phone": "+40 734 456 014", "address": "Bd. 21 Decembrie 1989 77",   "city": "Cluj-Napoca"},
    {"email": "vlad.neagu@outlook.com",       "password": "Vlad!N3agu",     "full_name": "Vlad Neagu",          "phone": "+40 735 567 015", "address": "Str. Brâncuși 9",            "city": "Cluj-Napoca"},
    {"email": "camelia.barbu@yahoo.com",      "password": "Cam3lia#B!",     "full_name": "Camelia Barbu",       "phone": "+40 736 678 016", "address": "Str. Albac 4",               "city": "Cluj-Napoca"},
    {"email": "george.lazar@gmail.com",       "password": "G3orge_Laz!",    "full_name": "George Lazăr",        "phone": "+40 737 789 017", "address": "Str. Mehedinți 21",          "city": "Cluj-Napoca"},
    {"email": "simona.dragomir@gmail.com",    "password": "Sim0na!Drag",    "full_name": "Simona Dragomir",     "phone": "+40 738 890 018", "address": "Str. Câmpeni 15",            "city": "Cluj-Napoca"},
    {"email": "dan.cristea@outlook.com",      "password": "Dan_Cr!st3a",    "full_name": "Dan Cristea",         "phone": "+40 739 901 019", "address": "Str. Closca 33",             "city": "Cluj-Napoca"},
    {"email": "admin@securbank.ro",           "password": "Admin!2026#",    "full_name": "Admin SecurBank",     "phone": "+40 740 000 000", "address": "Bd. Eroilor 1",              "city": "Cluj-Napoca"},
]


def _iban(user_idx):
    """Generate a deterministic but realistic Romanian IBAN."""
    # Format: RO + 2 check digits + 4 char bank code + 16 digit account
    bank_codes = ["RZSB", "BTRL", "BRDE", "INGB", "RNCB"]
    bank = bank_codes[user_idx % len(bank_codes)]
    acct = f"{1000000000000000 + user_idx * 7919:016d}"
    check = f"{50 + user_idx % 50:02d}"
    return f"RO{check}{bank}{acct}"


def _card_number(user_idx, card_idx):
    """Generate a deterministic fake Visa/Mastercard number."""
    prefix = "4532" if card_idx % 2 == 0 else "5412"  # Visa or MC
    body = f"{(user_idx * 1000 + card_idx * 137 + 100000):012d}"[-12:]
    return f"{prefix} {body[:4]} {body[4:8]} {body[8:12]}"


def _api_key():
    """Generate a random API key pair."""
    return f"sb_live_{secrets.token_hex(16)}", f"sk_{secrets.token_hex(32)}"


def run_seed():
    db = SessionLocal()

    for idx, u in enumerate(DEMO_USERS):
        # Skip if user already exists
        if db.query(User).filter(User.email == u["email"]).first():
            continue

        # ── Create User ──
        user = User(
            email=u["email"],
            password_hash=pwd_ctx.hash(u["password"]),
            full_name=u["full_name"],
            phone=u["phone"],
            address=u["address"],
            city=u["city"],
            country="Romania",
        )
        db.add(user)
        db.flush()  # get user.id

        # ── Create Bank Accounts (1-3 per user) ──
        account_types = ["checking", "savings", "business"]
        num_accounts = 1 + (idx % 3)  # 1, 2, or 3 accounts
        balances = [
            round(1500 + idx * 327.50 + 0.73, 2),
            round(8200 + idx * 1250.00 + 0.41, 2),
            round(25000 + idx * 4100.00 + 0.19, 2),
        ]
        currencies = ["RON", "EUR", "USD"]

        accounts = []
        for a_idx in range(num_accounts):
            acct = BankAccount(
                user_id=user.id,
                iban=_iban(idx * 3 + a_idx),
                account_type=account_types[a_idx],
                balance=balances[a_idx],
                currency=currencies[a_idx] if a_idx < 2 else "RON",
            )
            db.add(acct)
            db.flush()
            accounts.append(acct)

        # ── Create Cards (1 per account, some users get a virtual card too) ──
        card_types = ["debit", "credit", "virtual"]
        for c_idx, acct in enumerate(accounts):
            card = Card(
                user_id=user.id,
                account_id=acct.id,
                card_number=_card_number(idx, c_idx),
                card_holder=u["full_name"].upper(),
                expiry_date=f"{(idx % 12) + 1:02d}/{27 + c_idx % 3:02d}",
                cvv=f"{100 + idx * 13 + c_idx * 7:03d}"[-3:],
                card_type=card_types[c_idx % 3],
                daily_limit=5000.0 + idx * 500.0,
            )
            db.add(card)

        # Extra virtual card for every 3rd user
        if idx % 3 == 0 and accounts:
            vcard = Card(
                user_id=user.id,
                account_id=accounts[0].id,
                card_number=_card_number(idx, 99),
                card_holder=u["full_name"].upper(),
                expiry_date=f"{(idx % 12) + 1:02d}/28",
                cvv=f"{900 + idx:03d}"[-3:],
                card_type="virtual",
                daily_limit=1000.0,
            )
            db.add(vcard)

        # ── Create API Keys (0-2 per user) ──
        api_labels = [
            ("Mobile App", "read"),
            ("Trading Bot", "read+write"),
            ("Admin Dashboard", "full"),
        ]
        num_keys = idx % 3  # 0, 1, or 2 keys
        for k_idx in range(num_keys):
            key, secret = _api_key()
            label, perms = api_labels[k_idx]
            api_key = APIKey(
                user_id=user.id,
                key=key,
                secret=secret,
                label=label,
                permissions=perms,
                last_used=datetime.utcnow() - timedelta(hours=idx * 2 + k_idx),
            )
            db.add(api_key)

    db.commit()
    count = db.query(User).count()
    print(f"[OK] Seeded {count} users with accounts, cards, and API keys")
    db.close()


if __name__ == "__main__":
    run_seed()
