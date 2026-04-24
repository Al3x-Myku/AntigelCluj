"""SMS sender — mock adapter for phishing SMS messages."""

import logging

logger = logging.getLogger(__name__)


def send_sms(phone: str, body: str) -> bool:
    """Mock SMS sender — logs the message instead of sending."""
    if not phone:
        logger.warning("No phone number provided")
        return False

    logger.info(f"[MOCK SMS] To: {phone}")
    logger.info(f"[MOCK SMS] Body: {body[:100]}...")
    # In production, this would use Twilio:
    # from twilio.rest import Client
    # client = Client(ACCOUNT_SID, AUTH_TOKEN)
    # client.messages.create(to=phone, from_=FROM_NUMBER, body=body)
    return True
