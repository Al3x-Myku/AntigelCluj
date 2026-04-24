"""Campaign model — phishing campaign definition."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    name = Column(String(200), nullable=False)
    status = Column(
        Enum("draft", "queued", "running", "completed", "failed", name="campaign_status"),
        default="draft",
    )
    schedule_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    launched_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Channel toggles
    use_email = Column(Integer, default=1)
    use_sms = Column(Integer, default=0)
    use_whatsapp = Column(Integer, default=0)
    use_telegram = Column(Integer, default=0)
    use_discord = Column(Integer, default=0)
    use_instagram = Column(Integer, default=0)

    # Stats (cached counters for quick reads)
    total_targets = Column(Integer, default=0)
    total_sent = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    total_clicked = Column(Integer, default=0)
    total_submitted = Column(Integer, default=0)

    # Relationships
    messages = relationship("CampaignMessage", back_populates="campaign", cascade="all, delete-orphan")
    targets = relationship("Target", back_populates="campaign", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "uid": self.uid,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "launched_at": self.launched_at.isoformat() if self.launched_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "schedule_at": self.schedule_at.isoformat() if self.schedule_at else None,
            "channels": {
                "email": bool(self.use_email),
                "sms": bool(self.use_sms),
                "whatsapp": bool(self.use_whatsapp),
                "telegram": bool(self.use_telegram),
                "discord": bool(self.use_discord),
                "instagram": bool(self.use_instagram),
            },
            "stats": {
                "total_targets": self.total_targets,
                "total_sent": self.total_sent,
                "total_failed": self.total_failed,
                "total_clicked": self.total_clicked,
                "total_submitted": self.total_submitted,
            },
        }


class CampaignMessage(Base):
    __tablename__ = "campaign_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    channel = Column(
        Enum("email", "sms", "whatsapp", "telegram", "discord", "instagram", name="channel_type"),
        nullable=False,
    )
    subject = Column(String(500), nullable=True)  # Email subject
    body = Column(Text, nullable=False)  # Template body with {{vars}}

    campaign = relationship("Campaign", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "channel": self.channel,
            "subject": self.subject,
            "body": self.body,
        }
