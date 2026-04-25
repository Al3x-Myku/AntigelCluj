"""BankAccount document helpers — MongoDB."""

from datetime import datetime


def make_bank_account(user_id, iban, account_type, balance=0.0, currency="RON"):
    """Create a bank account document dict."""
    return {
        "user_id": user_id,
        "iban": iban,
        "account_type": account_type,
        "balance": balance,
        "currency": currency,
        "is_frozen": False,
        "created_at": datetime.utcnow(),
    }
