"""ServiceTicket model — maintenance and repair requests."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Text
from backend.database import Base


class ServiceTicket(Base):
    __tablename__ = "service_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False)
    assigned_tech_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticket_number = Column(String(20), unique=True, nullable=False)     # BT-20260001
    category = Column(String(50), nullable=False)                       # installation, repair, maintenance, warranty
    priority = Column(String(20), default="normal")                     # low, normal, high, urgent
    status = Column(String(20), default="open")                         # open, in_progress, completed, cancelled
    description = Column(Text, nullable=False)
    estimated_cost = Column(Float, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
