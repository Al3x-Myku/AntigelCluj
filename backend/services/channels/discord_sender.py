"""Discord sender — mock adapter for phishing via Discord webhook."""

import logging

logger = logging.getLogger(__name__)


def send_discord(user_id: str, body: str) -> bool:
    """Mock Discord sender — logs the message."""
    logger.info(f"[MOCK DISCORD] To: {user_id}")
    logger.info(f"[MOCK DISCORD] Body: {body[:100]}...")
    # In production:
    # import requests
    # WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    # requests.post(WEBHOOK_URL, json={"content": body})
    return True
