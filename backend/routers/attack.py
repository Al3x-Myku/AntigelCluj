"""Attack router — Campaign CRUD, launch, and live stats."""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from backend.database import get_db
from backend.models.campaign import Campaign, CampaignMessage
from backend.models.target import Target

router = APIRouter()


# ─── Create Campaign ─────────────────────────────────────────
@router.post("/campaigns")
async def create_campaign(
    name: str = Form(...),
    use_email: int = Form(1),
    use_sms: int = Form(0),
    use_whatsapp: int = Form(0),
    use_telegram: int = Form(0),
    use_discord: int = Form(0),
    use_instagram: int = Form(0),
    email_subject: Optional[str] = Form(None),
    email_body: Optional[str] = Form(None),
    sms_body: Optional[str] = Form(None),
    whatsapp_body: Optional[str] = Form(None),
    telegram_body: Optional[str] = Form(None),
    discord_body: Optional[str] = Form(None),
    instagram_body: Optional[str] = Form(None),
    schedule_at: Optional[str] = Form(None),
    targets_csv: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Create a new phishing campaign with targets and channel messages."""
    # Create campaign
    campaign = Campaign(
        name=name,
        use_email=use_email,
        use_sms=use_sms,
        use_whatsapp=use_whatsapp,
        use_telegram=use_telegram,
        use_discord=use_discord,
        use_instagram=use_instagram,
    )
    if schedule_at:
        try:
            campaign.schedule_at = datetime.fromisoformat(schedule_at)
        except ValueError:
            pass
    db.add(campaign)
    db.flush()

    # Add message templates
    channel_templates = {
        "email": (email_subject, email_body),
        "sms": (None, sms_body),
        "whatsapp": (None, whatsapp_body),
        "telegram": (None, telegram_body),
        "discord": (None, discord_body),
        "instagram": (None, instagram_body),
    }
    channel_flags = {
        "email": use_email,
        "sms": use_sms,
        "whatsapp": use_whatsapp,
        "telegram": use_telegram,
        "discord": use_discord,
        "instagram": use_instagram,
    }

    for channel, (subject, body) in channel_templates.items():
        if channel_flags.get(channel) and body:
            msg = CampaignMessage(
                campaign_id=campaign.id,
                channel=channel,
                subject=subject,
                body=body,
            )
            db.add(msg)

    # Parse CSV targets
    target_count = 0
    if targets_csv:
        content = await targets_csv.read()
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        for row in reader:
            # Normalize column names
            row = {k.strip().lower(): v.strip() for k, v in row.items() if v}
            target = Target(
                campaign_id=campaign.id,
                first_name=row.get("first_name", row.get("firstname", "")),
                last_name=row.get("last_name", row.get("lastname", "")),
                email=row.get("email", ""),
                phone=row.get("phone", ""),
            )
            db.add(target)
            target_count += 1

    campaign.total_targets = target_count
    db.commit()
    db.refresh(campaign)

    return {"status": "created", "campaign": campaign.to_dict()}


# ─── List Campaigns ──────────────────────────────────────────
@router.get("/campaigns")
async def list_campaigns(db: Session = Depends(get_db)):
    campaigns = db.query(Campaign).order_by(Campaign.created_at.desc()).all()
    return {"campaigns": [c.to_dict() for c in campaigns]}


# ─── Get Campaign Detail ─────────────────────────────────────
@router.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = (
        db.query(Campaign)
        .options(joinedload(Campaign.messages), joinedload(Campaign.targets))
        .filter(Campaign.id == campaign_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    data = campaign.to_dict()
    data["messages"] = [m.to_dict() for m in campaign.messages]
    data["targets"] = [t.to_dict() for t in campaign.targets]
    return data


# ─── Launch Campaign ─────────────────────────────────────────
@router.post("/campaigns/{campaign_id}/launch")
async def launch_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if campaign.status not in ("draft", "failed"):
        raise HTTPException(status_code=400, detail=f"Campaign is already {campaign.status}")

    campaign.status = "queued"
    campaign.launched_at = datetime.utcnow()
    db.commit()

    # Try RQ, fall back to sync
    try:
        from backend.services.campaign_runner import enqueue_campaign
        enqueue_campaign(campaign.id)
    except Exception:
        # Fallback: run synchronously
        from backend.services.campaign_runner import run_campaign
        run_campaign(campaign.id)

    db.refresh(campaign)
    return {"status": "launched", "campaign": campaign.to_dict()}


# ─── Live Stats ───────────────────────────────────────────────
@router.get("/stats/{campaign_id}")
async def campaign_stats(campaign_id: int, db: Session = Depends(get_db)):
    campaign = (
        db.query(Campaign)
        .options(joinedload(Campaign.targets))
        .filter(Campaign.id == campaign_id)
        .first()
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    targets = campaign.targets

    # Per-channel stats
    channels = ["email", "sms", "whatsapp", "telegram", "discord", "instagram"]
    per_channel = {}
    for ch in channels:
        ch_targets = [t for t in targets if t.channel_used == ch]
        per_channel[ch] = {
            "sent": sum(1 for t in ch_targets if t.status in ("sent", "clicked", "submitted")),
            "failed": sum(1 for t in ch_targets if t.status == "failed"),
            "clicked": sum(1 for t in ch_targets if t.status in ("clicked", "submitted")),
            "submitted": sum(1 for t in ch_targets if t.status == "submitted"),
            "pending": sum(1 for t in ch_targets if t.status == "pending"),
        }

    # Timeline (messages sent over time — group by hour)
    timeline = {}
    for t in targets:
        if t.sent_at:
            hour_key = t.sent_at.strftime("%Y-%m-%d %H:00")
            ch = t.channel_used or "email"
            if hour_key not in timeline:
                timeline[hour_key] = {}
            timeline[hour_key][ch] = timeline[hour_key].get(ch, 0) + 1

    # Funnel
    total = len(targets)
    sent = sum(1 for t in targets if t.status in ("sent", "clicked", "submitted"))
    clicked = sum(1 for t in targets if t.status in ("clicked", "submitted"))
    submitted = sum(1 for t in targets if t.status == "submitted")

    # Heatmap (success by hour of day)
    heatmap = {}
    for t in targets:
        if t.clicked_at:
            h = t.clicked_at.hour
            heatmap[h] = heatmap.get(h, 0) + 1

    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "totals": {
            "targets": total,
            "sent": sent,
            "failed": sum(1 for t in targets if t.status == "failed"),
            "clicked": clicked,
            "submitted": submitted,
            "pending": sum(1 for t in targets if t.status == "pending"),
        },
        "per_channel": per_channel,
        "funnel": [
            {"stage": "Targets", "count": total},
            {"stage": "Sent", "count": sent},
            {"stage": "Clicked", "count": clicked},
            {"stage": "Submitted", "count": submitted},
        ],
        "timeline": timeline,
        "heatmap": heatmap,
    }
