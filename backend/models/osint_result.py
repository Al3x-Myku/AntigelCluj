"""OSINT Result model — scraped contact from web reconnaissance."""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, Text
from backend.database import Base


class OsintScan(Base):
    __tablename__ = "osint_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    domain = Column(String(200), nullable=False)
    company_name = Column(String(300), nullable=True)
    status = Column(String(20), default="running")  # running, completed, failed
    total_emails = Column(Integer, default=0)
    total_phones = Column(Integer, default=0)
    total_contacts = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    log = Column(Text, default="")  # newline-separated log entries

    def to_dict(self):
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "domain": self.domain,
            "company_name": self.company_name,
            "status": self.status,
            "total_emails": self.total_emails,
            "total_phones": self.total_phones,
            "total_contacts": self.total_contacts,
            "duration_seconds": round(self.duration_seconds, 2),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class OsintResult(Base):
    __tablename__ = "osint_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scan_id = Column(String(36), index=True, nullable=False)
    email = Column(String(200), nullable=True)
    phone = Column(String(30), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company = Column(String(300), nullable=True)
    domain = Column(String(200), nullable=True)
    department = Column(String(100), nullable=True)
    role = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    confidence = Column(Float, default=0.5)  # 0.0-1.0
    risk_score = Column(Float, default=0.5)  # 0.0-1.0
    ai_summary = Column(Text, nullable=True)   # AI-generated enrichment summary
    scraped_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "email": self.email,
            "phone": self.phone,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "name": f"{self.first_name or ''} {self.last_name or ''}".strip(),
            "company": self.company,
            "domain": self.domain,
            "department": self.department,
            "role": self.role,
            "source_url": self.source_url,
            "confidence": round(self.confidence, 2),
            "risk_score": round(self.risk_score, 2),
            "ai_summary": self.ai_summary or "",
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }
