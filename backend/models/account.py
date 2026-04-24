"""Account and related resource models — for lockdown system."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from backend.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(200), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True)
    is_locked = Column(Boolean, default=False)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    usual_ip = Column(String(45), nullable=True)  # For geo-distance calc
    usual_city = Column(String(100), default="Cluj-Napoca")
    usual_country = Column(String(50), default="Romania")

    # Relationships
    cards = relationship("Card", back_populates="account", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="account", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="account", cascade="all, delete-orphan")
    api_tokens = relationship("ApiToken", back_populates="account", cascade="all, delete-orphan")

    def to_dict(self, include_resources=False):
        d = {
            "id": self.id,
            "uid": self.uid,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "is_locked": self.is_locked,
            "locked_at": self.locked_at.isoformat() if self.locked_at else None,
        }
        if include_resources:
            d["cards"] = [c.to_dict() for c in self.cards]
            d["sessions"] = [s.to_dict() for s in self.sessions]
            d["subscriptions"] = [sub.to_dict() for sub in self.subscriptions]
            d["api_tokens"] = [t.to_dict() for t in self.api_tokens]
        return d


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    card_number_masked = Column(String(20), nullable=False)  # e.g. **** **** **** 1234
    card_type = Column(String(20), default="visa")  # visa, mastercard
    status = Column(
        Enum("active", "frozen", "expired", name="card_status"),
        default="active",
    )
    frozen_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="cards")

    def to_dict(self):
        return {
            "id": self.id,
            "card_number_masked": self.card_number_masked,
            "card_type": self.card_type,
            "status": self.status,
            "frozen_at": self.frozen_at.isoformat() if self.frozen_at else None,
        }


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    session_token = Column(String(64), default=lambda: uuid.uuid4().hex, unique=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    status = Column(
        Enum("active", "revoked", name="session_status"),
        default="active",
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="sessions")

    def to_dict(self):
        return {
            "id": self.id,
            "session_token": self.session_token[:8] + "...",
            "ip_address": self.ip_address,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    plan_name = Column(String(100), nullable=False)
    status = Column(
        Enum("active", "suspended", "cancelled", name="subscription_status"),
        default="active",
    )
    suspended_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="subscriptions")

    def to_dict(self):
        return {
            "id": self.id,
            "plan_name": self.plan_name,
            "status": self.status,
            "suspended_at": self.suspended_at.isoformat() if self.suspended_at else None,
        }


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    token_name = Column(String(100), nullable=False)
    token_hash = Column(String(64), default=lambda: uuid.uuid4().hex)
    status = Column(
        Enum("active", "revoked", name="token_status"),
        default="active",
    )
    revoked_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="api_tokens")

    def to_dict(self):
        return {
            "id": self.id,
            "token_name": self.token_name,
            "status": self.status,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    triggered_by = Column(String(50), default="system")  # system, operator, auto

    def to_dict(self):
        return {
            "id": self.id,
            "account_id": self.account_id,
            "action": self.action,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "triggered_by": self.triggered_by,
        }
