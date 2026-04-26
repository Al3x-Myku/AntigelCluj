"""Defense router — Login monitoring, anomaly detection, bans, and lockdown."""
# noinspection PyBroadException

import random
import logging

logger = logging.getLogger(__name__)
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models.login_event import LoginEvent
from backend.models.account import Account, AuditLog
from backend.services import anomaly_detector, rate_limiter
from backend.services.lockdown import execute_lockdown, get_lockdown_status, restore_account
from backend.services.external_lockdown import lockdown_external_sites, restore_external_sites, get_external_status

router = APIRouter()


# ─── Login Events ─────────────────────────────────────────────
@router.get("/events")
async def get_events(
    limit: int = Query(50, le=200),
    account_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get recent login events with anomaly scores."""
    q = db.query(LoginEvent).order_by(desc(LoginEvent.timestamp))
    if account_id:
        q = q.filter(LoginEvent.account_id == account_id)
    events = q.limit(limit).all()
    return {"events": [e.to_dict() for e in events]}


# ─── Anomalies Only ───────────────────────────────────────────
@router.get("/anomalies")
async def get_anomalies(
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    """Get flagged anomalous events only."""
    events = (
        db.query(LoginEvent)
        .filter(LoginEvent.is_anomalous == True)
        .order_by(desc(LoginEvent.timestamp))
        .limit(limit)
        .all()
    )
    return {"anomalies": [e.to_dict() for e in events]}


# ─── Train/Retrain Model ─────────────────────────────────────
@router.post("/train")
async def train_model(db: Session = Depends(get_db)):
    """Train the MCD anomaly detector on historical login data.
    
    Selects training events by their *feature values* (not the is_anomalous flag)
    to avoid the chicken-and-egg problem where a bad model marks normal events anomalous.
    """
    # Select events with normal-looking features regardless of how they were scored
    events = db.query(LoginEvent).filter(
        LoginEvent.ip_is_new == 0.0,
        LoginEvent.device_is_new == 0.0,
        LoginEvent.geo_distance_km < 100.0,
        LoginEvent.login_failures_last_hour < 3.0,
        LoginEvent.success == True,
    ).all()
    if len(events) < 10:
        raise HTTPException(status_code=400, detail=f"Need at least 10 normal events, have {len(events)}")

    vectors = [e.feature_vector() for e in events]
    stats = anomaly_detector.train_model(vectors)
    return {"status": "trained", "stats": stats}


# ─── Score All Unscored Events ────────────────────────────────
@router.post("/score")
async def score_events(db: Session = Depends(get_db)):
    """Score all unscored login events."""
    events = db.query(LoginEvent).filter(LoginEvent.anomaly_score == None).all()
    if not events:
        return {"scored": 0}

    vectors = [e.feature_vector() for e in events]
    results = anomaly_detector.score_batch(vectors)

    for evt, (score, is_anom) in zip(events, results):
        evt.anomaly_score = score
        evt.is_anomalous = is_anom

    db.commit()
    return {"scored": len(events), "anomalies_found": sum(1 for _, a in results if a)}


# Auto-lockdown state
AUTO_LOCKDOWN_ENABLED = False

@router.post("/auto-lockdown")
async def toggle_auto_lockdown(enabled: bool = Query(...)):
    """Toggle the Blue Team automatic lockdown response."""
    global AUTO_LOCKDOWN_ENABLED
    AUTO_LOCKDOWN_ENABLED = enabled
    return {"status": "success", "auto_lockdown_enabled": AUTO_LOCKDOWN_ENABLED}

@router.get("/auto-lockdown")
async def get_auto_lockdown():
    """Get the current Auto-lockdown state."""
    return {"auto_lockdown_enabled": AUTO_LOCKDOWN_ENABLED}

# ─── Simulate Login (for demo) ───────────────────────────────
@router.post("/simulate-login")
async def simulate_login(
    account_id: Optional[int] = None,
    is_attack: bool = False,
    db: Session = Depends(get_db),
):
    """Inject a simulated login event for demo purposes."""
    if account_id:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
    else:
        accounts = db.query(Account).all()
        account = random.choice(accounts)

    now = datetime.utcnow()

    if is_attack:
        # Suspicious login - make it very unusual so Mahalanobis catches it clearly
        attacker_ips = ["45.33.32.156", "185.220.101.1", "91.219.237.42"]
        city, country = random.choice([("Moscow", "Russia"), ("Beijing", "China"), ("Lagos", "Nigeria"), ("Karachi", "Pakistan")])
        evt = LoginEvent(
            account_id=account.id,
            username=account.username,
            ip_address=random.choice(attacker_ips),
            timestamp=now,
            success=random.choice([True, False]),
            hour_of_day=round(random.uniform(2, 4), 2), # 2-4 AM offset heavily penalized
            day_of_week=float(random.choice([5, 6])),
            login_failures_last_hour=float(random.randint(4, 12)),
            ip_is_new=1.0,
            device_is_new=1.0,
            geo_distance_km=round(random.uniform(800, 5000), 2),
            time_since_last_login_hrs=round(random.uniform(0.01, 0.3), 4),
            typing_speed_ms=round(random.uniform(10, 25), 2),
            device_fingerprint=f"attacker-{random.randint(1000, 9999)}",
            country=country,
            city=city,
        )
    else:
        # Normal login - tightly aligned with our synthetic generator (9 AM or 1:30 PM, clean metrics)
        evt = LoginEvent(
            account_id=account.id,
            username=account.username,
            ip_address=account.usual_ip or "192.168.1.10",
            timestamp=now,
            success=True, # Normal is almost always successful
            hour_of_day=round(random.choice([9.0, 13.5]) + random.uniform(-0.2, 0.2), 2),
            day_of_week=float(now.weekday() % 5), # 0-4 weekday
            login_failures_last_hour=0.0,
            ip_is_new=0.0,
            device_is_new=0.0,
            geo_distance_km=round(random.uniform(0, 5), 2),
            time_since_last_login_hrs=round(random.uniform(12, 24), 2),
            typing_speed_ms=round(random.gauss(100, 10), 2),
            device_fingerprint=f"dev-{account.id}-main",
            country="Romania",
            city="Cluj-Napoca",
        )

    # Score the event
    score, is_anom = anomaly_detector.score_event(evt.feature_vector())
    evt.anomaly_score = score
    evt.is_anomalous = is_anom

    # Ban Logic / Rate Limiting
    ban_info = None
    if not evt.success:
        # Basic rate limiter catch for failures
        ban_info = rate_limiter.record_failure(evt.ip_address, evt.username)

    # Auto-ban IP definitively if fraudulent anomaly detected
    if is_anom:
        ban_info = rate_limiter.apply_explicit_ban(evt.ip_address, "Fraudulent Anomaly Detected")

    db.add(evt)
    db.commit()
    db.refresh(evt)

    result = evt.to_dict()
    if ban_info:
        result["ban_triggered"] = ban_info

    # Auto-lockdown account if anomalous
    logger.info(f"Simulate-login result: is_anom={is_anom}, score={score}, auto_lockdown={AUTO_LOCKDOWN_ENABLED}")
    if is_anom and AUTO_LOCKDOWN_ENABLED:
        threshold = anomaly_detector.get_threshold()
        if score >= threshold:
            try:
                execute_lockdown(db, account.id, triggered_by="auto-response")
                result["auto_lockdown_triggered"] = True
                result["auto_lockdown_warning"] = f"Account locked. Score {score} exceeds threshold {threshold}. IP banned."
                # ─── CASCADE: Lock down on external mockup sites ───
                try:
                    ext_results = lockdown_external_sites(account.email)
                    result["external_lockdowns"] = ext_results
                except Exception as e:
                    logger.error(f"External lockdown cascade failed: {e}")
                    result["external_lockdown_error"] = str(e)
            except Exception as e:
                logger.error(f"Internal lockdown failed: {e}")
                result["auto_lockdown_triggered"] = False
                result["auto_lockdown_error"] = str(e)
        else:
            result["auto_lockdown_warning"] = f"Anomaly score {score} below threshold {threshold}. IP banned but account not locked."
    elif is_anom:
        result["auto_lockdown_warning"] = f"Anomaly score {score}. IP banned. Enable Auto-lockdown to lock account as well."

    return result


# ─── Lockdown ─────────────────────────────────────────────────
@router.post("/lockdown/{account_id}")
async def lockdown_account(account_id: int, db: Session = Depends(get_db)):
    """Execute full lockdown on an account — cascades to external systems."""
    try:
        result = execute_lockdown(db, account_id, triggered_by="operator")
        # Cascade to external sites
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            try:
                ext_results = lockdown_external_sites(account.email)
                result["external_lockdowns"] = ext_results
            except Exception as e:
                result["external_lockdown_error"] = str(e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/lockdown/{account_id}/status")
async def lockdown_status(account_id: int, db: Session = Depends(get_db)):
    """Get lockdown status and resource tree for an account."""
    try:
        return get_lockdown_status(db, account_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/lockdown/{account_id}/restore")
async def restore(account_id: int, db: Session = Depends(get_db)):
    """Restore a locked-down account — cascades restore to external systems."""
    try:
        result = restore_account(db, account_id, triggered_by="operator")
        # Cascade restore to external sites
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            try:
                ext_results = restore_external_sites(account.email)
                result["external_restores"] = ext_results
            except Exception:
                pass
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ─── External Systems Status ─────────────────────────────────
@router.get("/external-status")
async def external_systems_status():
    """Get health/status of all registered external lockdown targets."""
    return {"systems": get_external_status()}


# ─── Bans ─────────────────────────────────────────────────────
@router.get("/bans")
async def get_bans():
    """Get all current IP/user bans."""
    bans = rate_limiter.get_all_bans()
    return {"bans": bans, "total": len(bans)}


@router.delete("/bans/{ip}")
async def clear_ban(ip: str):
    """Clear a ban for a specific IP."""
    rate_limiter.clear_ban(ip=ip)
    return {"status": "cleared", "ip": ip}


# ─── Dashboard Stats ──────────────────────────────────────────
@router.get("/dashboard")
async def defense_dashboard(db: Session = Depends(get_db)):
    """Get overview stats for the defense dashboard."""
    total_events = db.query(LoginEvent).count()
    anomalies = db.query(LoginEvent).filter(LoginEvent.is_anomalous == True).count()
    locked_accounts = db.query(Account).filter(Account.is_locked == True).count()
    active_accounts = db.query(Account).filter(Account.is_active == True).count()
    bans = rate_limiter.get_all_bans()
    recent_alerts = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .limit(10)
        .all()
    )

    # Score distribution for histogram
    scored_events = db.query(LoginEvent).filter(LoginEvent.anomaly_score != None).all()
    score_distribution = [e.anomaly_score for e in scored_events]

    return {
        "total_events": total_events,
        "total_anomalies": anomalies,
        "locked_accounts": locked_accounts,
        "active_accounts": active_accounts,
        "active_bans": len(bans),
        "bans": bans,
        "recent_alerts": [a.to_dict() for a in recent_alerts],
        "score_distribution": score_distribution,
        "threshold": anomaly_detector.get_threshold(),
    }


# ─── Accounts List ────────────────────────────────────────────
@router.get("/accounts")
async def list_accounts(db: Session = Depends(get_db)):
    """List all accounts with their lock status."""
    accounts = db.query(Account).all()
    return {"accounts": [a.to_dict(include_resources=True) for a in accounts]}
