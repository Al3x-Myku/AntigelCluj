"""BankAccount model — user bank accounts with IBAN."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey
from backend.database import Base


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    iban = Column(String(34), unique=True, nullable=False)
    account_type = Column(String(20), nullable=False)       # checking, savings, business
    balance = Column(Float, default=0.0)
    currency = Column(String(3), default="RON")
    is_frozen = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
