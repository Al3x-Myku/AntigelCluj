"""WhatsApp sender — uses Twilio WhatsApp API for phishing messages.

Twilio WhatsApp requires:
  1. A Twilio account with WhatsApp sandbox enabled
  2. Targets must have joined the sandbox first by sending
     "join <your-sandbox-keyword>" to the Twilio WhatsApp number
  3. Or, for production, a registered & approved WhatsApp Business API number

The FROM number must be prefixed with "whatsapp:" (e.g., "whatsapp:+14155238886")

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
TWILIO_WA_FROM = os.getenv("TWILIO_WHATSAPP_NUMBER", "")  # e.g. whatsapp:+14155238886


def send_whatsapp(phone: str, body: str) -> bool:
    """Send a WhatsApp message via Twilio, or log if not configured."""
    if not phone:
        logger.warning("No phone number provided for WhatsApp")
        return False

    # Normalize phone number
    phone = phone.strip()
    if not phone.startswith("+"):
        if phone.startswith("0"):
            phone = "+40" + phone[1:]
        else:
            phone = "+40" + phone

    # Twilio WhatsApp requires "whatsapp:" prefix
    wa_to = f"whatsapp:{phone}"
    wa_from = TWILIO_WA_FROM
    if wa_from and not wa_from.startswith("whatsapp:"):
        wa_from = f"whatsapp:{wa_from}"

    # If Twilio is not configured, use mock
    if not TWILIO_SID or not TWILIO_TOKEN or not wa_from:
        logger.info(f"📲 [WhatsApp → {phone}] {body[:120]}...")
        print(f"📲 [WHATSAPP MOCK] → {phone}: {body[:120]}...")
        return True

    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
        data = urllib.parse.urlencode({
            "From": wa_from,
            "To": wa_to,
            "Body": body,
        }).encode()

        req = urllib.request.Request(url, data=data, method="POST")
        credentials = base64.b64encode(f"{TWILIO_SID}:{TWILIO_TOKEN}".encode()).decode()
        req.add_header("Authorization", f"Basic {credentials}")

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            sid = result.get("sid", "unknown")
            logger.info(f"📲 WhatsApp sent to {phone} (SID: {sid})")
            return True

    except Exception as e:
        logger.error(f"WhatsApp failed to {phone}: {e}")
        return False
