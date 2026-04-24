"""Target model — individual phishing target within a campaign."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship
from backend.database import Base


class Target(Base):
    __tablename__ = "targets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    token = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)

    # Contact info
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)

    # Tracking
    status = Column(
        Enum("pending", "sent", "failed", "clicked", "submitted", name="target_status"),
        default="pending",
    )
    channel_used = Column(String(20), nullable=True)  # Which channel actually delivered
    sent_at = Column(DateTime, nullable=True)
    clicked_at = Column(DateTime, nullable=True)
    submitted_at = Column(DateTime, nullable=True)

    # Captured credentials (for demo — stored as plain text in demo mode)
    captured_username = Column(String(200), nullable=True)
    captured_password = Column(String(200), nullable=True)

    # Extra
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationship
    campaign = relationship("Campaign", back_populates="targets")

    def to_dict(self):
        return {
            "id": self.id,
            "token": self.token,
            "name": f"{self.first_name or ''} {self.last_name or ''}".strip(),
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "channel_used": self.channel_used,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "clicked_at": self.clicked_at.isoformat() if self.clicked_at else None,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "captured_username": self.captured_username,
            "ip_address": self.ip_address,
        }
