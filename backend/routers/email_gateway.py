"""Email Gateway router — email defense API for scanning, quarantine, and deletion."""

import os
import logging
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models.quarantined_email import QuarantinedEmail
from backend.services.email_scanner import scan_email, scan_raw_eml
from backend.services.email_remover import (
    delete_email, scan_captured_emails_dir
)

logger = logging.getLogger(__name__)
router = APIRouter()


class EmailScanRequest(BaseModel):
    subject: str = ""
    body: str = ""
    from_addr: str = ""
    to_addr: str = ""
    reply_to: str = ""
    headers: Optional[dict] = None
    attachments: Optional[List[str]] = None
    raw_eml: Optional[str] = None  # Alternative: raw .eml content


class EmailDeleteRequest(BaseModel):
    quarantine_id: str = ""
    message_id: str = ""
    subject: str = ""
    to_addr: str = ""


# ─── Scan Email ──────────────────────────────────────────────
@router.post("/email/scan")
async def scan_email_endpoint(req: EmailScanRequest, db: Session = Depends(get_db)):
    """Scan email content for phishing indicators and auto-quarantine if suspicious."""

    if req.raw_eml:
        verdict = scan_raw_eml(req.raw_eml)
        from_addr = req.from_addr
        to_addr = req.to_addr
        subject = req.subject
    else:
        verdict = scan_email(
            subject=req.subject,
            body=req.body,
            from_addr=req.from_addr,
            to_addr=req.to_addr,
            reply_to=req.reply_to,
            headers=req.headers,
            attachments=req.attachments,
        )
        from_addr = req.from_addr
        to_addr = req.to_addr
        subject = req.subject

    # Auto-quarantine if suspicious or dangerous
    quarantine_record = None
    if verdict.risk_level in ("suspicious", "dangerous"):
        qe = QuarantinedEmail(
            from_addr=from_addr or "unknown",
            to_addr=to_addr or "unknown",
            subject=subject,
            body_preview=(req.body or "")[:500],
            scan_score=verdict.score,
            risk_level=verdict.risk_level,
            recommendation=verdict.recommendation,
            status="quarantined",
        )
        qe.set_flags(verdict.flags)
        db.add(qe)
        db.commit()
        db.refresh(qe)
        quarantine_record = qe.to_dict()
        logger.warning(f"📧 Email quarantined: {subject[:60]} (score={verdict.score})")

    return {
        "verdict": verdict.to_dict(),
        "quarantined": quarantine_record is not None,
        "quarantine_record": quarantine_record,
    }


# ─── Scan All Captured Emails ────────────────────────────────
@router.post("/email/scan-captured")
async def scan_captured_emails(db: Session = Depends(get_db)):
    """Scan all .eml files in captured_emails/ directory and quarantine suspicious ones."""
    captured = scan_captured_emails_dir()
    if not captured:
        return {"scanned": 0, "flagged": 0, "message": "No captured emails found"}

    scanned = 0
    flagged = 0
    results = []

    for eml_info in captured:
        try:
            filepath = eml_info["filepath"]
            with open(filepath, "r", errors="replace") as f:
                raw = f.read()

            verdict = scan_raw_eml(raw)
            scanned += 1

            entry = {
                "filename": eml_info["filename"],
                "from": eml_info["from"],
                "to": eml_info["to"],
                "subject": eml_info["subject"],
                "score": verdict.score,
                "risk_level": verdict.risk_level,
                "flags": verdict.flags,
            }

            if verdict.risk_level in ("suspicious", "dangerous"):
                flagged += 1
                # Check if already quarantined
                existing = db.query(QuarantinedEmail).filter(
                    QuarantinedEmail.subject == eml_info["subject"],
                    QuarantinedEmail.from_addr == eml_info["from"],
                    QuarantinedEmail.status == "quarantined",
                ).first()

                if not existing:
                    qe = QuarantinedEmail(
                        message_id=eml_info.get("message_id", ""),
                        from_addr=eml_info["from"],
                        to_addr=eml_info["to"],
                        subject=eml_info["subject"],
                        body_preview=f"File: {eml_info['filename']}",
                        scan_score=verdict.score,
                        risk_level=verdict.risk_level,
                        recommendation=verdict.recommendation,
                        source_file=filepath,
                        status="quarantined",
                    )
                    qe.set_flags(verdict.flags)
                    db.add(qe)

            results.append(entry)

        except Exception as e:
            logger.error(f"Error scanning {eml_info.get('filename')}: {e}")

    db.commit()
    return {"scanned": scanned, "flagged": flagged, "results": results}


# ─── Quarantine List ─────────────────────────────────────────
@router.get("/email/quarantine")
async def list_quarantine(
    limit: int = Query(50, le=200),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all quarantined/flagged emails."""
    q = db.query(QuarantinedEmail).order_by(desc(QuarantinedEmail.scanned_at))
    if status:
        q = q.filter(QuarantinedEmail.status == status)
    records = q.limit(limit).all()
    return {"quarantine": [r.to_dict() for r in records], "total": len(records)}


# ─── Delete Flagged Email ────────────────────────────────────
@router.post("/email/delete")
async def delete_flagged_email(req: EmailDeleteRequest, db: Session = Depends(get_db)):
    """Delete a flagged email from the recipient's mailbox."""
    # Find the quarantine record
    qe = None
    if req.quarantine_id:
        qe = db.query(QuarantinedEmail).filter(
            QuarantinedEmail.quarantine_id == req.quarantine_id
        ).first()
    if not qe and req.message_id:
        qe = db.query(QuarantinedEmail).filter(
            QuarantinedEmail.message_id == req.message_id
        ).first()

    if not qe:
        raise HTTPException(404, "Quarantined email not found")

    if qe.status == "deleted":
        return {"status": "already_deleted", "quarantine_id": qe.quarantine_id}

    # Perform deletion
    result = delete_email(
        message_id=qe.message_id or "",
        subject=qe.subject or "",
        to_addr=qe.to_addr or "",
        source_file=qe.source_file or "",
    )

    if result["success"]:
        qe.status = "deleted"
        qe.deleted_at = datetime.utcnow()
        db.commit()
        logger.info(f"🗑️ Email deleted: {qe.subject[:60]}")

    return {
        "status": "deleted" if result["success"] else "failed",
        "quarantine_id": qe.quarantine_id,
        "deletion_result": result,
    }


# ─── Bulk Delete All Flagged ─────────────────────────────────
@router.post("/email/delete-all-flagged")
async def delete_all_flagged(db: Session = Depends(get_db)):
    """Delete all quarantined emails (dangerous + suspicious) from mailboxes."""
    records = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.status == "quarantined"
    ).all()

    deleted = 0
    failed = 0
    for qe in records:
        result = delete_email(
            message_id=qe.message_id or "",
            subject=qe.subject or "",
            to_addr=qe.to_addr or "",
            source_file=qe.source_file or "",
        )
        if result["success"]:
            qe.status = "deleted"
            qe.deleted_at = datetime.utcnow()
            deleted += 1
        else:
            failed += 1

    db.commit()
    return {"deleted": deleted, "failed": failed, "total": len(records)}


# ─── Release Email ───────────────────────────────────────────
@router.post("/email/release")
async def release_email(req: EmailDeleteRequest, db: Session = Depends(get_db)):
    """Release a quarantined email (mark as safe / false positive)."""
    qe = None
    if req.quarantine_id:
        qe = db.query(QuarantinedEmail).filter(
            QuarantinedEmail.quarantine_id == req.quarantine_id
        ).first()

    if not qe:
        raise HTTPException(404, "Quarantined email not found")

    qe.status = "released"
    qe.released_at = datetime.utcnow()
    db.commit()

    return {"status": "released", "quarantine_id": qe.quarantine_id}


# ─── Stats ───────────────────────────────────────────────────
@router.get("/email/stats")
async def email_stats(db: Session = Depends(get_db)):
    """Get email scanning/defense statistics."""
    total = db.query(QuarantinedEmail).count()
    quarantined = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.status == "quarantined").count()
    deleted = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.status == "deleted").count()
    released = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.status == "released").count()
    dangerous = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.risk_level == "dangerous").count()
    suspicious = db.query(QuarantinedEmail).filter(
        QuarantinedEmail.risk_level == "suspicious").count()

    # Captured emails on disk
    from pathlib import Path
    captured_dir = Path(__file__).parent.parent / "captured_emails"
    captured_count = len(list(captured_dir.glob("*.eml"))) if captured_dir.exists() else 0

    return {
        "total_scanned": total,
        "quarantined": quarantined,
        "deleted": deleted,
        "released": released,
        "dangerous": dangerous,
        "suspicious": suspicious,
        "captured_on_disk": captured_count,
        "prevention_rate": round(deleted / max(total, 1) * 100, 1),
    }
