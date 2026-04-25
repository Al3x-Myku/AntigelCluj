"""Card model — debit/credit cards linked to bank accounts."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, ForeignKey
from backend.database import Base


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    card_number = Column(String(19), unique=True, nullable=False)   # masked: **** **** **** 1234
    card_holder = Column(String(255), nullable=False)
    expiry_date = Column(String(5), nullable=False)                 # MM/YY
    cvv = Column(String(4), nullable=False)
    card_type = Column(String(20), nullable=False)                  # debit, credit, virtual
    daily_limit = Column(Float, default=5000.0)
    is_frozen = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
