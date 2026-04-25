"""User model — customers, technicians, admins."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Boolean
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50))
    address = Column(String(500))
    city = Column(String(100))
    country = Column(String(100), default="Romania")
    role = Column(String(20), default="customer")       # customer, technician, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
