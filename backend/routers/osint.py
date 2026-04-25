"""OSINT router — OSINT scanning, results, and campaign generation endpoints."""

import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.osint_result import OsintScan, OsintResult

router = APIRouter()


class ScanRequest(BaseModel):
    domain: str
    company_name: Optional[str] = ""


class GenerateCampaignRequest(BaseModel):
    scan_id: str
    campaign_name: Optional[str] = None
    channels: Optional[Dict[str, bool]] = None


# ─── Start OSINT Scan ────────────────────────────────────────
@router.post("/osint/scan")
async def start_scan(req: ScanRequest, db: Session = Depends(get_db)):
    """Start an OSINT scan for a target domain."""
    domain = req.domain.strip().lower()
    if not domain or "." not in domain:
        raise HTTPException(400, "Invalid domain (e.g., 'example.com')")

    from backend.services.osint_scraper import start_osint_scan
    scan_id = start_osint_scan(domain, req.company_name or "")

    return {"status": "started", "scan_id": scan_id, "domain": domain}


# ─── List All Scans ──────────────────────────────────────────
@router.get("/osint/scans")
async def list_scans(db: Session = Depends(get_db)):
    """List all OSINT scans."""
    scans = db.query(OsintScan).order_by(OsintScan.started_at.desc()).all()
    return {"scans": [s.to_dict() for s in scans]}


# ─── Get Scan Results ────────────────────────────────────────
@router.get("/osint/results/{scan_id}")
async def get_scan_results(scan_id: str, db: Session = Depends(get_db)):
    """Get OSINT scan details and results."""
    scan = db.query(OsintScan).filter(OsintScan.scan_id == scan_id).first()
    if not scan:
        raise HTTPException(404, "Scan not found")

    results = db.query(OsintResult).filter(
        OsintResult.scan_id == scan_id
    ).order_by(OsintResult.risk_score.desc()).all()

    return {
        "scan": scan.to_dict(),
        "results": [r.to_dict() for r in results],
        "log": scan.log or "",
    }


# ─── Export Results as CSV ───────────────────────────────────
@router.get("/osint/results/{scan_id}/csv")
async def export_csv(scan_id: str, db: Session = Depends(get_db)):
    """Download OSINT results as CSV file."""
    scan = db.query(OsintScan).filter(OsintScan.scan_id == scan_id).first()
    if not scan:
        raise HTTPException(404, "Scan not found")

    from backend.services.campaign_generator import generate_campaign_csv
    csv_content = generate_campaign_csv(scan_id)

    return StreamingResponse(
        io.BytesIO(csv_content.encode("utf-8")),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="osint_{scan.domain}_{scan_id[:8]}.csv"'
        },
    )


# ─── Generate Campaign from Scan ────────────────────────────
@router.post("/osint/generate-campaign")
async def generate_campaign(req: GenerateCampaignRequest, db: Session = Depends(get_db)):
    """Auto-create a phishing campaign from OSINT scan results."""
    try:
        from backend.services.campaign_generator import create_campaign_from_scan
        campaign = create_campaign_from_scan(
            scan_id=req.scan_id,
            campaign_name=req.campaign_name,
            channels=req.channels,
        )
        return {"status": "created", "campaign": campaign}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Campaign generation failed: {str(e)}")
