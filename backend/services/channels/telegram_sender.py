"""Telegram sender — uses Telegram Bot API to send phishing messages.

Requires:
  1. Create a bot via @BotFather → get TELEGRAM_BOT_TOKEN
  2. Targets must have started a conversation with the bot first
     (Telegram bots can't initiate DMs — the user must /start first)
  3. The "chat_id" for each target is their Telegram numeric user ID

Falls back to mock logging if TELEGRAM_BOT_TOKEN is not configured.
"""

import os
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def send_telegram(chat_id: str, body: str) -> bool:
    """Send a Telegram message via Bot API, or log if not configured."""
    if not chat_id:
        logger.warning("No Telegram chat_id provided")
        return False

    # If Telegram bot token is not configured, use mock
    if not TELEGRAM_BOT_TOKEN:
        logger.info(f"💬 [Telegram → {chat_id}] {body[:120]}...")
        print(f"💬 [TELEGRAM MOCK] → {chat_id}: {body[:120]}...")
        return True

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        # Strip HTML tags for Telegram (or keep and use parse_mode=HTML)
        # Telegram supports basic HTML: <b>, <i>, <a href="">, <code>
        payload = json.dumps({
            "chat_id": chat_id,
            "text": body,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,  # Show link preview (good for phishing)
        }).encode()

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                msg_id = result["result"]["message_id"]
                logger.info(f"💬 Telegram message sent to {chat_id} (msg_id: {msg_id})")
                return True
            else:
                logger.error(f"Telegram API error: {result.get('description')}")
                return False

    except Exception as e:
        logger.error(f"Telegram failed to {chat_id}: {e}")
        return False


def get_telegram_updates() -> list:
    """Get recent messages to the bot (useful for finding chat_ids)."""
    if not TELEGRAM_BOT_TOKEN:
        return []
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        with urllib.request.urlopen(url, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get("result", [])
    except Exception:
        return []
