"""User model — SQLAlchemy ORM for BreezeTech (MySQL/MariaDB)."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(String(300), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(50), default="Romania")
    role = Column(String(20), default="customer")  # customer, technician, admin
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "phone": self.phone,
            "city": self.city,
            "role": self.role,
            "is_active": self.is_active,
            "is_locked": self.is_locked,
            "locked_at": self.locked_at.isoformat() if self.locked_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
