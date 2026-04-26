"""Service Ticket model — SQLAlchemy ORM for BreezeTech."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, ForeignKey
from backend.database import Base


class ServiceTicket(Base):
    __tablename__ = "service_tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"), nullable=True)
    assigned_tech_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ticket_number = Column(String(20), unique=True, nullable=False)
    category = Column(String(30), nullable=False)  # installation, repair, maintenance, warranty
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    status = Column(String(20), default="open")  # open, in_progress, completed
    description = Column(Text, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    completed_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "ticket_number": self.ticket_number,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "description": self.description,
            "estimated_cost": self.estimated_cost,
        }
