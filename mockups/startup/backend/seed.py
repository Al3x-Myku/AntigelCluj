"""Seed script — create 20 demo users with AC devices, service tickets, and API keys."""

import os
import sys
import secrets
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from passlib.context import CryptContext
from backend.database import SessionLocal, init_db
from backend.models.user import User
from backend.models.device import Device
from backend.models.service_ticket import ServiceTicket
from backend.models.api_key import APIKey

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 20 Demo Users ──────────────────────────────────────────────────────────
DEMO_USERS = [
    # 15 Customers
    {"email": "radu.gheorghe@gmail.com",       "password": "Radu!Gh30rg",     "full_name": "Radu Gheorghe",        "phone": "+40 721 100 001", "address": "Str. Avram Iancu 22",       "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "alina.muresan@yahoo.com",       "password": "Al1na#Mures",     "full_name": "Alina Mureșan",        "phone": "+40 722 200 002", "address": "Bd. Eroilor 10",             "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "cosmin.dragomir@gmail.com",     "password": "C0sm!n_Drag",     "full_name": "Cosmin Dragomir",      "phone": "+40 723 300 003", "address": "Str. Napoca 45",             "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "bianca.pop@outlook.com",        "password": "Bianc@Pop26",     "full_name": "Bianca Pop",           "phone": "+40 724 400 004", "address": "Str. Memorandumului 12",     "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "florin.neag@gmail.com",         "password": "Fl0rin!Neag",     "full_name": "Florin Neag",          "phone": "+40 725 500 005", "address": "Calea Moților 88",           "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "oana.barbu@yahoo.com",          "password": "0ana_Barbu!",     "full_name": "Oana Barbu",           "phone": "+40 726 600 006", "address": "Str. Republicii 30",         "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "tudor.lazarescu@gmail.com",     "password": "Tud0r#Laz!",      "full_name": "Tudor Lăzărescu",      "phone": "+40 727 700 007", "address": "Str. Dorobanților 17",       "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "isabela.rusu@protonmail.com",   "password": "Is4bela!Rus",     "full_name": "Isabela Rusu",         "phone": "+40 728 800 008", "address": "Str. Clinicilor 9",          "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "marius.ciobanu@gmail.com",      "password": "Mar1us#Ciob",     "full_name": "Marius Ciobanu",       "phone": "+40 729 900 009", "address": "Str. Observatorului 55",     "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "denisa.dumitriu@yahoo.com",     "password": "Den!sa_Dum1",     "full_name": "Denisa Dumitriu",      "phone": "+40 730 010 010", "address": "Aleea Detunata 7",           "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "sergiu.tanase@gmail.com",       "password": "S3rg1u!Tan",      "full_name": "Sergiu Tănase",        "phone": "+40 731 110 011", "address": "Str. Pasteur 22",            "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "carmen.ilie@outlook.com",       "password": "Carm3n#Ili!",     "full_name": "Carmen Ilie",          "phone": "+40 732 220 012", "address": "Str. Piezișă 6",             "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "paul.matei@gmail.com",          "password": "P4ul_Mat3i!",     "full_name": "Paul Matei",           "phone": "+40 733 330 013", "address": "Str. Fabricii 41",           "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "andreea.nicolescu@yahoo.com",   "password": "Andr33a!Nic",     "full_name": "Andreea Nicolescu",    "phone": "+40 734 440 014", "address": "Bd. 21 Decembrie 1989 33",   "city": "Cluj-Napoca",  "role": "customer"},
    {"email": "liviu.patrascu@gmail.com",      "password": "L1viu#Patr!",     "full_name": "Liviu Pătrașcu",       "phone": "+40 735 550 015", "address": "Str. Brâncuși 14",           "city": "Cluj-Napoca",  "role": "customer"},
    # 3 Technicians
    {"email": "alex.service@breezetech.ro",    "password": "T3ch_Al3x!",      "full_name": "Alexandru Serviciu",   "phone": "+40 740 001 001", "address": "Str. Fabricii 2",            "city": "Cluj-Napoca",  "role": "technician"},
    {"email": "ionut.hvac@breezetech.ro",      "password": "Hvac!Ion1t",      "full_name": "Ionuț Manole",         "phone": "+40 740 002 002", "address": "Str. Fabricii 2",            "city": "Cluj-Napoca",  "role": "technician"},
    {"email": "darius.tech@breezetech.ro",     "password": "Dar!us_T3ch",     "full_name": "Darius Petrescu",      "phone": "+40 740 003 003", "address": "Str. Fabricii 2",            "city": "Cluj-Napoca",  "role": "technician"},
    # 2 Admins
    {"email": "ceo@breezetech.ro",             "password": "C3O!Breeze26",    "full_name": "Victor Antonescu",     "phone": "+40 740 000 100", "address": "Str. Fabricii 2",            "city": "Cluj-Napoca",  "role": "admin"},
    {"email": "admin@breezetech.ro",           "password": "Adm!n_BT2026",   "full_name": "Admin BreezeTech",     "phone": "+40 740 000 200", "address": "Str. Fabricii 2",            "city": "Cluj-Napoca",  "role": "admin"},
]


# ── AC Unit Data ────────────────────────────────────────────────────────────
AC_BRANDS = [
    ("Daikin",     ["FTXM25R", "FTXM35R", "FTXM50R", "FTXA50AW"]),
    ("Mitsubishi", ["MSZ-AP25VG", "MSZ-LN35VG", "MSZ-EF42VE", "MFZ-KT50VE"]),
    ("Samsung",    ["AR09TXHQASIN", "AR12TXHQASIN", "AR18TXFCAWKN", "AC071RNCDKG"]),
    ("LG",         ["S09ET", "S12ET", "S18ET", "A12LL"]),
    ("Gree",       ["BORA-09", "FAIRY-12", "U-CROWN-18", "CLIVIA-24"]),
]

LOCATIONS = [
    "Living Room", "Bedroom", "Master Bedroom", "Kitchen", "Office",
    "Conference Room A", "Conference Room B", "Server Room", "Reception",
    "Kids Room", "Guest Room", "Studio", "Attic", "Basement", "Garage",
]

MODES = ["cooling", "heating", "auto", "fan", "dry"]
BTU_OPTIONS = [9000, 12000, 18000, 24000]
FIRMWARE_VERSIONS = ["3.2.1", "3.1.0", "2.9.4", "3.3.0-beta", "2.8.7"]


# ── Ticket data ─────────────────────────────────────────────────────────────
TICKET_CATEGORIES = ["installation", "repair", "maintenance", "warranty"]
TICKET_PRIORITIES = ["low", "normal", "high", "urgent"]
TICKET_DESCRIPTIONS = [
    "New split AC unit installation in living room — need wall mounting and drainage setup.",
    "Unit is making a loud rattling noise when switching to heating mode.",
    "Annual filter cleaning and refrigerant pressure check.",
    "Compressor stopped working after 8 months — should be under warranty.",
    "Remote control unresponsive, need pairing reset.",
    "Water leaking from indoor unit onto the floor.",
    "Thermostat display is blank, unit doesn't respond to commands.",
    "Scheduled seasonal maintenance before summer.",
    "AC unit blowing warm air even in cooling mode. Possible refrigerant leak.",
    "Request firmware update for smart home integration.",
    "Outdoor unit fan is not spinning, makes clicking sound.",
    "Installation of second unit in bedroom, need electrical work.",
    "Ice forming on evaporator coils during normal operation.",
    "Annual inspection and performance certificate for warranty renewal.",
    "WiFi module not connecting to home network after router change.",
]


def _serial(brand_code, idx):
    """Generate a deterministic serial number."""
    return f"BT-{brand_code[:2].upper()}-{2024000 + idx:07d}"


def _api_key():
    """Generate a random API key pair."""
    return f"bt_live_{secrets.token_hex(16)}", f"btsk_{secrets.token_hex(32)}"


def run_seed():
    init_db()
    db = SessionLocal()
    tech_ids = []
    customer_ids = []

    for idx, u in enumerate(DEMO_USERS):
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
            role=u["role"],
        )
        db.add(user)
        db.flush()

        if u["role"] == "technician":
            tech_ids.append(user.id)
        elif u["role"] == "customer":
            customer_ids.append(user.id)

        # ── Create AC Devices (customers only: 1-4 units each) ──
        if u["role"] == "customer":
            num_devices = 1 + (idx % 4)
            for d_idx in range(num_devices):
                brand, models = AC_BRANDS[(idx + d_idx) % len(AC_BRANDS)]
                model = models[(idx + d_idx) % len(models)]
                device = Device(
                    user_id=user.id,
                    serial_number=_serial(brand, idx * 10 + d_idx),
                    model_name=model,
                    brand=brand,
                    location=LOCATIONS[(idx * 3 + d_idx) % len(LOCATIONS)],
                    install_date=datetime.utcnow() - timedelta(days=90 + idx * 30 + d_idx * 15),
                    btu_rating=BTU_OPTIONS[d_idx % len(BTU_OPTIONS)],
                    target_temp=round(20.0 + (idx % 6) * 0.5, 1),
                    current_temp=round(21.0 + (idx % 8) * 0.3 + d_idx * 0.2, 1),
                    mode=MODES[(idx + d_idx) % len(MODES)],
                    is_online=not (idx == 4 and d_idx == 0),  # one device offline for demo
                    firmware_version=FIRMWARE_VERSIONS[(idx + d_idx) % len(FIRMWARE_VERSIONS)],
                )
                db.add(device)
            db.flush()

        # ── Create API Keys (some users get IoT integration keys) ──
        if u["role"] in ("customer", "admin"):
            api_labels = [
                ("Smart Home Hub", "read+write"),
                ("HVAC Controller", "full"),
                ("Mobile App", "read"),
            ]
            num_keys = idx % 3
            for k_idx in range(num_keys):
                key, secret = _api_key()
                label, perms = api_labels[k_idx]
                api_key = APIKey(
                    user_id=user.id,
                    key=key,
                    secret=secret,
                    label=label,
                    permissions=perms,
                    last_used=datetime.utcnow() - timedelta(hours=idx * 3 + k_idx),
                )
                db.add(api_key)

    db.flush()

    # ── Create Service Tickets ──
    # Grab all devices for ticket assignment
    all_devices = db.query(Device).all()
    if tech_ids and all_devices:
        statuses = ["open", "in_progress", "completed", "completed", "open", "in_progress"]
        for t_idx, device in enumerate(all_devices[:15]):  # 15 tickets
            ticket = ServiceTicket(
                user_id=device.user_id,
                device_id=device.id,
                assigned_tech_id=tech_ids[t_idx % len(tech_ids)] if t_idx % 3 != 0 else None,
                ticket_number=f"BT-{2026:04d}{t_idx + 1:04d}",
                category=TICKET_CATEGORIES[t_idx % len(TICKET_CATEGORIES)],
                priority=TICKET_PRIORITIES[t_idx % len(TICKET_PRIORITIES)],
                status=statuses[t_idx % len(statuses)],
                description=TICKET_DESCRIPTIONS[t_idx % len(TICKET_DESCRIPTIONS)],
                estimated_cost=round(150.0 + t_idx * 45.50, 2) if t_idx % 2 == 0 else None,
                scheduled_date=datetime.utcnow() + timedelta(days=t_idx * 2 - 5) if t_idx % 3 != 2 else None,
                completed_date=datetime.utcnow() - timedelta(days=3) if statuses[t_idx % len(statuses)] == "completed" else None,
            )
            db.add(ticket)

    db.commit()
    count = db.query(User).count()
    devices = db.query(Device).count()
    tickets = db.query(ServiceTicket).count()
    keys = db.query(APIKey).count()
    print(f"[OK] Seeded {count} users, {devices} AC devices, {tickets} service tickets, {keys} API keys")
    db.close()


if __name__ == "__main__":
    run_seed()
