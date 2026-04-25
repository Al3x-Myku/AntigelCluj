"""Device model — AC units registered to customers."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey
from backend.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    serial_number = Column(String(30), unique=True, nullable=False)
    model_name = Column(String(100), nullable=False)
    brand = Column(String(50), nullable=False)
    location = Column(String(200), nullable=False)          # "Living Room", "Office B2", etc.
    install_date = Column(DateTime, nullable=False)
    btu_rating = Column(Integer, nullable=False)             # 9000, 12000, 18000, 24000
    target_temp = Column(Float, default=22.0)                # °C
    current_temp = Column(Float, default=23.5)               # °C
    mode = Column(String(20), default="cooling")             # cooling, heating, auto, fan, dry
    is_online = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    firmware_version = Column(String(20), default="3.2.1")
    created_at = Column(DateTime, default=datetime.utcnow)
