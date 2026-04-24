"""Campaign runner — sends phishing messages across all enabled channels."""

import os
import logging
from datetime import datetime
from backend.database import SessionLocal
from backend.models.campaign import Campaign, CampaignMessage
from backend.models.target import Target

logger = logging.getLogger(__name__)

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


def enqueue_campaign(campaign_id: int):
    """Enqueue campaign job to Redis Queue."""
    try:
        import redis
        from rq import Queue
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        conn = redis.from_url(redis_url)
        q = Queue("phishguard", connection=conn)
        q.enqueue(run_campaign, campaign_id, job_timeout="30m")
        logger.info(f"Campaign {campaign_id} enqueued to RQ")
    except Exception as e:
        logger.warning(f"RQ unavailable ({e}), running synchronously")
        run_campaign(campaign_id)


def run_campaign(campaign_id: int):
    """Execute campaign — send messages to all targets on all enabled channels."""
    db = SessionLocal()
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return

        campaign.status = "running"
        db.commit()

        targets = db.query(Target).filter(Target.campaign_id == campaign_id).all()
        messages = db.query(CampaignMessage).filter(CampaignMessage.campaign_id == campaign_id).all()
        msg_by_channel = {m.channel: m for m in messages}

        # Determine which channels to use
        channel_map = {
            "email": campaign.use_email,
            "sms": campaign.use_sms,
            "whatsapp": campaign.use_whatsapp,
            "telegram": campaign.use_telegram,
            "discord": campaign.use_discord,
            "instagram": campaign.use_instagram,
            "calendar": getattr(campaign, 'use_calendar', False),
        }

        active_channels = [ch for ch, enabled in channel_map.items() if enabled]
        if not active_channels:
            active_channels = ["email"]

        sent_count = 0
        failed_count = 0

        for target in targets:
            # Pick the first active channel that has a message template
            channel_used = None
            for ch in active_channels:
                if ch in msg_by_channel:
                    channel_used = ch
                    break
            if not channel_used:
                channel_used = active_channels[0]

            # Build the phish link
            phish_link = f"{BASE_URL}/phish/{target.token}"

            # Get message template and substitute variables
            msg_template = msg_by_channel.get(channel_used)
            body = msg_template.body if msg_template else f"Please verify your account: {phish_link}"
            subject = msg_template.subject if msg_template else "Action Required: Account Verification"

            # Variable substitution
            body = substitute_vars(body, target, phish_link)
            subject = substitute_vars(subject, target, phish_link)

            # Send via channel
            try:
                success = send_via_channel(channel_used, target, subject, body, phish_link)
                if success:
                    target.status = "sent"
                    target.sent_at = datetime.utcnow()
                    target.channel_used = channel_used
                    sent_count += 1
                else:
                    target.status = "failed"
                    target.channel_used = channel_used
                    failed_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {target.email}: {e}")
                target.status = "failed"
                target.channel_used = channel_used
                failed_count += 1

            db.commit()

        # Update campaign counters
        campaign.total_sent = sent_count
        campaign.total_failed = failed_count
        campaign.status = "completed"
        campaign.completed_at = datetime.utcnow()
        db.commit()
        logger.info(f"Campaign {campaign_id} complete: {sent_count} sent, {failed_count} failed")

    except Exception as e:
        logger.error(f"Campaign {campaign_id} error: {e}")
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if campaign:
            campaign.status = "failed"
            db.commit()
    finally:
        db.close()


def substitute_vars(text: str, target: Target, phish_link: str) -> str:
    """Replace {{var}} placeholders in message templates."""
    replacements = {
        "{{name}}": f"{target.first_name or ''} {target.last_name or ''}".strip(),
        "{{first_name}}": target.first_name or "",
        "{{last_name}}": target.last_name or "",
        "{{email}}": target.email or "",
        "{{link}}": phish_link,
        "{{bank}}": "SecureBank International",
        "{{company}}": "PhishGuard Corp",
    }
    for key, val in replacements.items():
        text = text.replace(key, val)
    return text


def send_via_channel(channel: str, target: Target, subject: str, body: str, phish_link: str) -> bool:
    """Route message to the appropriate channel sender."""
    if channel == "email":
        from backend.services.channels.email_sender import send_email
        return send_email(target.email, subject, body)
    elif channel == "sms":
        from backend.services.channels.sms_sender import send_sms
        return send_sms(target.phone, body)
    elif channel == "telegram":
        from backend.services.channels.telegram_sender import send_telegram
        return send_telegram(target.email, body)
    elif channel == "discord":
        from backend.services.channels.discord_sender import send_discord
        return send_discord(target.email, body)
    elif channel == "whatsapp":
        from backend.services.channels.sms_sender import send_sms  # WhatsApp uses same mock
        return send_sms(target.phone, body)
    elif channel == "instagram":
        from backend.services.channels.instagram_sender import send_instagram
        return send_instagram(target.email, body)
    elif channel == "calendar":
        from backend.services.channels.calendar_sender import send_calendar_invite
        target_name = f"{target.first_name or ''} {target.last_name or ''}".strip()
        return send_calendar_invite(
            to_email=target.email,
            to_name=target_name or target.email,
            subject=subject,
            body_html=body,
            phish_url=phish_link,
        )
    else:
        logger.warning(f"Unknown channel: {channel}")
        return False
