"""SMS sender — Twilio API for phishing SMS messages.

Falls back to mock logging if TWILIO_ACCOUNT_SID is not configured.
"""

import os
import logging
import urllib.request
import urllib.parse
import base64
import json

logger = logging.getLogger(__name__)

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER", "")  # e.g. +14155552671


def send_sms(phone: str, body: str) -> bool:
    """Send an SMS via Twilio, or log if not configured."""
    if not phone:
        logger.warning("No phone number provided")
        return False

    # Normalize phone number — ensure +country code
    phone = phone.strip()
    if not phone.startswith("+"):
        # Default to Romania (+40)
        if phone.startswith("0"):
            phone = "+40" + phone[1:]
        else:
            phone = "+40" + phone

    # If Twilio is not configured, use mock
    if not TWILIO_SID or not TWILIO_TOKEN or not TWILIO_FROM:
        logger.info(f"📱 [SMS → {phone}] {body[:120]}...")
        print(f"📱 [SMS MOCK] → {phone}: {body[:120]}...")
        return True

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        data = urllib.parse.urlencode({
            "From": TWILIO_FROM,
            "To": phone,
            "Body": body,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        credentials = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
        req.add_header("Authorization", f"Basic {credentials}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            sid = result.get("sid", "unknown")
            logger.info(f"📱 SMS sent to {phone} (SID: {sid})")
            return True

    except Exception as e:
        logger.error(f"SMS failed to {phone}: {e}")
        return False
