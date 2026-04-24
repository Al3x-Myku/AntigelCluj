"""Instagram sender — mock adapter for phishing via Instagram DM."""

import logging

logger = logging.getLogger(__name__)


def send_instagram(user_id: str, body: str) -> bool:
    """Mock Instagram DM sender — logs the message."""
    logger.info(f"[MOCK INSTAGRAM] To: {user_id}")
    logger.info(f"[MOCK INSTAGRAM] Body: {body[:100]}...")
    # In production: use Instagram Graph API / Basic Display API
    return True
