"""QuarantinedEmail model — stores scanned/quarantined phishing emails."""

import uuid
import json
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from backend.database import Base


class QuarantinedEmail(Base):
    __tablename__ = "quarantined_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    quarantine_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    message_id = Column(String(500), nullable=True)  # Email Message-ID header

    # Envelope
    from_addr = Column(String(300), nullable=False)
    to_addr = Column(String(300), nullable=False)
    reply_to = Column(String(300), nullable=True)
    subject = Column(String(1000), nullable=True)
    body_preview = Column(Text, nullable=True)  # First 500 chars of body

    # Scan results
    scan_score = Column(Float, default=0.0)  # 0.0 – 1.0
    risk_level = Column(String(20), default="safe")  # safe, suspicious, dangerous
    flags = Column(Text, default="[]")  # JSON array of flag strings
    recommendation = Column(String(200), nullable=True)

    # Status
    status = Column(String(20), default="quarantined")  # quarantined, deleted, released
    source_file = Column(String(500), nullable=True)  # path to .eml if local mode

    # Timestamps
    scanned_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    released_at = Column(DateTime, nullable=True)

    def get_flags(self):
        """Return flags as a Python list."""
        try:
            return json.loads(self.flags) if self.flags else []
        except (json.JSONDecodeError, TypeError):
            return []

    def set_flags(self, flag_list):
        """Set flags from a Python list."""
        self.flags = json.dumps(flag_list)

    def to_dict(self):
        return {
            "id": self.id,
            "quarantine_id": self.quarantine_id,
            "message_id": self.message_id,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "reply_to": self.reply_to,
            "subject": self.subject,
            "body_preview": self.body_preview,
            "scan_score": round(self.scan_score, 4) if self.scan_score else 0.0,
            "risk_level": self.risk_level,
            "flags": self.get_flags(),
            "recommendation": self.recommendation,
            "status": self.status,
            "scanned_at": self.scanned_at.isoformat() if self.scanned_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
            "released_at": self.released_at.isoformat() if self.released_at else None,
        }
