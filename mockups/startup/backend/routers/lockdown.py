"""Lockdown router — BreezeTech (MySQL/MariaDB).

Exposes API endpoints that PhishGuard can call to freeze accounts,
disable devices, and revoke API keys when an anomaly is detected.
"""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.device import Device
from backend.models.api_key import APIKey

router = APIRouter()


@router.get("/users")
def list_users(db: Session = Depends(get_db)):
    """List all users with their lock status — used by PhishGuard for account mapping."""
    users = db.query(User).all()
    result = []
    for u in users:
        devices = db.query(Device).filter(Device.user_id == u.id).all()
        api_keys = db.query(APIKey).filter(APIKey.user_id == u.id).all()
        result.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "is_locked": u.is_locked,
            "locked_at": u.locked_at.isoformat() if u.locked_at else None,
            "devices": [{"id": d.id, "serial": d.serial_number, "brand": d.brand, "model": d.model_name, "is_online": d.is_online} for d in devices],
            "api_keys": [{"id": k.id, "label": k.label, "is_active": k.is_active} for k in api_keys],
        })
    return {"users": result}


@router.post("/{user_id}")
def lockdown_user(user_id: int, db: Session = Depends(get_db)):
    """Execute full lockdown on a BreezeTech user account.

    1. Disable user login (is_active=False, is_locked=True)
    2. Take all IoT devices offline
    3. Revoke all API keys
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    actions = []

    # 1. Disable account
    user.is_active = False
    user.is_locked = True
    user.locked_at = now
    actions.append("account_disabled")

    # 2. Take devices offline
    devices = db.query(Device).filter(Device.user_id == user_id, Device.is_online == True).all()
    for d in devices:
        d.is_online = False
    actions.append(f"devices_offline:{len(devices)}")

    # 3. Revoke API keys
    api_keys = db.query(APIKey).filter(APIKey.user_id == user_id, APIKey.is_active == True).all()
    for k in api_keys:
        k.is_active = False
    actions.append(f"api_keys_revoked:{len(api_keys)}")

    db.commit()

    return {
        "status": "locked",
        "user_id": user_id,
        "email": user.email,
        "full_name": user.full_name,
        "locked_at": now.isoformat(),
        "actions": actions,
    }


@router.post("/{user_id}/restore")
def restore_user(user_id: int, db: Session = Depends(get_db)):
    """Restore a locked-down BreezeTech user account."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = True
    user.is_locked = False

    # Bring devices back online
    devices = db.query(Device).filter(Device.user_id == user_id).all()
    for d in devices:
        d.is_online = True

    # Re-activate API keys
    api_keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()
    for k in api_keys:
        k.is_active = True

    db.commit()

    return {"status": "restored", "user_id": user_id, "email": user.email}


@router.get("/{user_id}/status")
def lockdown_status(user_id: int, db: Session = Depends(get_db)):
    """Get lockdown status for a specific user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    devices = db.query(Device).filter(Device.user_id == user_id).all()
    api_keys = db.query(APIKey).filter(APIKey.user_id == user_id).all()

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_locked": user.is_locked,
        "locked_at": user.locked_at.isoformat() if user.locked_at else None,
        "devices": [d.to_dict() for d in devices],
        "api_keys": [k.to_dict() for k in api_keys],
    }
