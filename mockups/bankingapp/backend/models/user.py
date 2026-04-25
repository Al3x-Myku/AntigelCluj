"""User document helpers — MongoDB."""

from datetime import datetime


def make_user(email, password_hash, full_name, phone=None, address=None, city=None, country="Romania"):
    """Create a user document dict."""
    return {
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "phone": phone,
        "address": address,
        "city": city,
        "country": country,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
