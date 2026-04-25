"""APIKey document helpers — MongoDB."""

from datetime import datetime


def make_api_key(user_id, key, secret, label, permissions="read", last_used=None):
    """Create an API key document dict."""
    return {
        "user_id": user_id,
        "key": key,
        "secret": secret,
        "label": label,
        "permissions": permissions,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_used": last_used,
    }
