"""Telegram sender — mock adapter for phishing via Telegram Bot API."""

import logging

logger = logging.getLogger(__name__)


def send_telegram(chat_id: str, body: str) -> bool:
    """Mock Telegram sender — logs the message."""
    logger.info(f"[MOCK TELEGRAM] To: {chat_id}")
    logger.info(f"[MOCK TELEGRAM] Body: {body[:100]}...")
    # In production:
    # import requests
    # BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    # requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    #               json={"chat_id": chat_id, "text": body, "parse_mode": "HTML"})
    return True
