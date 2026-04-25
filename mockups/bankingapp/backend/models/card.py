"""Card document helpers — MongoDB."""

from datetime import datetime


def make_card(user_id, account_id, card_number, card_holder, expiry_date, cvv,
              card_type="debit", daily_limit=5000.0):
    """Create a card document dict."""
    return {
        "user_id": user_id,
        "account_id": account_id,
        "card_number": card_number,
        "card_holder": card_holder,
        "expiry_date": expiry_date,
        "cvv": cvv,
        "card_type": card_type,
        "daily_limit": daily_limit,
        "is_frozen": False,
        "created_at": datetime.utcnow(),
    }
