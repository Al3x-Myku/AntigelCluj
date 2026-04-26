"""Device (Smart AC Unit) model — SQLAlchemy ORM for BreezeTech."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey
from backend.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    serial_number = Column(String(50), unique=True, nullable=False)
    model_name = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=False)
    location = Column(String(100), nullable=True)
    install_date = Column(DateTime, nullable=True)
    btu_rating = Column(Integer, default=12000)
    target_temp = Column(Float, default=22.0)
    current_temp = Column(Float, default=22.0)
    mode = Column(String(20), default="auto")  # cooling, heating, auto, fan, dry
    is_online = Column(Boolean, default=True)
    firmware_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "serial_number": self.serial_number,
            "model_name": self.model_name,
            "brand": self.brand,
            "location": self.location,
            "btu_rating": self.btu_rating,
            "target_temp": self.target_temp,
            "current_temp": self.current_temp,
            "mode": self.mode,
            "is_online": self.is_online,
            "firmware_version": self.firmware_version,
        }
