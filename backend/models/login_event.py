"""LoginEvent model — records every login attempt with feature vector for anomaly detection."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean
from backend.database import Base


class LoginEvent(Base):
    __tablename__ = "login_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    success = Column(Boolean, default=False)

    # Feature vector components (8 features for Mahalanobis)
    hour_of_day = Column(Float, nullable=False)
    day_of_week = Column(Float, nullable=False)
    login_failures_last_hour = Column(Float, default=0)
    ip_is_new = Column(Float, default=0)  # 0 or 1
    device_is_new = Column(Float, default=0)  # 0 or 1
    geo_distance_km = Column(Float, default=0)
    time_since_last_login_hrs = Column(Float, default=0)
    typing_speed_ms = Column(Float, default=100)

    # Anomaly detection results
    anomaly_score = Column(Float, nullable=True)  # Mahalanobis distance
    is_anomalous = Column(Boolean, default=False)
    anomaly_engine = Column(String(20), default="sklearn")  # sklearn or onnx

    # Extra context
    user_agent = Column(String(500), nullable=True)
    device_fingerprint = Column(String(100), nullable=True)
    country = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)

    def feature_vector(self):
        """Return the 8-feature vector for anomaly scoring."""
        return [
            self.hour_of_day,
            self.day_of_week,
            self.login_failures_last_hour,
            self.ip_is_new,
            self.device_is_new,
            self.geo_distance_km,
            self.time_since_last_login_hrs,
            self.typing_speed_ms,
        ]

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "username": self.username,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "success": self.success,
            "features": {
                "hour_of_day": self.hour_of_day,
                "day_of_week": self.day_of_week,
                "login_failures_last_hour": self.login_failures_last_hour,
                "ip_is_new": self.ip_is_new,
                "device_is_new": self.device_is_new,
                "geo_distance_km": self.geo_distance_km,
                "time_since_last_login_hrs": self.time_since_last_login_hrs,
                "typing_speed_ms": self.typing_speed_ms,
            },
            "anomaly_score": round(self.anomaly_score, 4) if self.anomaly_score else None,
            "is_anomalous": self.is_anomalous,
            "anomaly_engine": self.anomaly_engine,
            "country": self.country,
            "city": self.city,
        }
