"""API Key model — SQLAlchemy ORM for BreezeTech."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey
from backend.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(100), unique=True, nullable=False)
    secret = Column(String(200), nullable=False)
    label = Column(String(100), nullable=False)
    permissions = Column(String(50), default="read")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "key": self.key[:12] + "...",
            "label": self.label,
            "permissions": self.permissions,
            "is_active": self.is_active,
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }
