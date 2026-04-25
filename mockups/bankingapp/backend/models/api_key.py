"""APIKey model — developer/integration API keys."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from backend.database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    key = Column(String(64), unique=True, nullable=False)
    secret = Column(String(128), nullable=False)
    label = Column(String(100), nullable=False)             # "Mobile App", "Trading Bot", etc.
    permissions = Column(String(255), default="read")       # read, read+write, full
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
