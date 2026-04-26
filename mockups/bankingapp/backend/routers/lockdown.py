"""Lockdown router — SecurBank Banking App (MongoDB).

Exposes API endpoints that PhishGuard can call to freeze accounts,
freeze cards, freeze bank accounts, and revoke API keys when an
anomaly is detected.
"""

from datetime import datetime
from fastapi import APIRouter, HTTPException
from bson import ObjectId

from backend.database import users_col, cards_col, bank_accounts_col, api_keys_col

router = APIRouter()


def _serialize_user(user):
    """Convert a MongoDB user document to a JSON-safe dict."""
    if not user:
        return None
    return {
        "id": str(user["_id"]),
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "is_active": user.get("is_active", True),
        "is_locked": user.get("is_locked", False),
        "locked_at": user.get("locked_at").isoformat() if user.get("locked_at") else None,
    }


@router.get("/users")
def list_users():
    """List all users with their lock/freeze status — used by PhishGuard for account mapping."""
    users = list(users_col.find())
    result = []
    for u in users:
        uid = str(u["_id"])
        user_cards = list(cards_col.find({"user_id": uid}))
        user_keys = list(api_keys_col.find({"user_id": uid}))
        user_accounts = list(bank_accounts_col.find({"user_id": uid}))
        result.append({
            "id": uid,
            "email": u.get("email"),
            "full_name": u.get("full_name"),
            "is_active": u.get("is_active", True),
            "is_locked": u.get("is_locked", False),
            "locked_at": u.get("locked_at").isoformat() if u.get("locked_at") else None,
            "cards": [{"id": str(c["_id"]), "number": c.get("card_number", "")[-4:], "type": c.get("card_type"), "is_frozen": c.get("is_frozen", False)} for c in user_cards],
            "bank_accounts": [{"id": str(a["_id"]), "iban": a.get("iban"), "is_frozen": a.get("is_frozen", False)} for a in user_accounts],
            "api_keys": [{"id": str(k["_id"]), "label": k.get("label"), "is_active": k.get("is_active", True)} for k in user_keys],
        })
    return {"users": result}


@router.post("/{user_id}")
def lockdown_user(user_id: str):
    """Execute full lockdown on a SecurBank user account.

    1. Disable user login (is_active=False, is_locked=True)
    2. Freeze all cards
    3. Freeze all bank accounts
    4. Revoke all API keys
    """
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = users_col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    actions = []

    # 1. Disable account
    users_col.update_one({"_id": oid}, {"$set": {"is_active": False, "is_locked": True, "locked_at": now}})
    actions.append("account_disabled")

    # 2. Freeze cards
    card_result = cards_col.update_many({"user_id": user_id, "is_frozen": False}, {"$set": {"is_frozen": True, "frozen_at": now}})
    actions.append(f"cards_frozen:{card_result.modified_count}")

    # 3. Freeze bank accounts
    acct_result = bank_accounts_col.update_many({"user_id": user_id, "is_frozen": False}, {"$set": {"is_frozen": True, "frozen_at": now}})
    actions.append(f"accounts_frozen:{acct_result.modified_count}")

    # 4. Revoke API keys
    key_result = api_keys_col.update_many({"user_id": user_id, "is_active": True}, {"$set": {"is_active": False, "revoked_at": now}})
    actions.append(f"api_keys_revoked:{key_result.modified_count}")

    return {
        "status": "locked",
        "user_id": user_id,
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "locked_at": now.isoformat(),
        "actions": actions,
    }


@router.post("/{user_id}/restore")
def restore_user(user_id: str):
    """Restore a locked-down SecurBank user account."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = users_col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Restore user
    users_col.update_one({"_id": oid}, {"$set": {"is_active": True, "is_locked": False}})

    # Unfreeze cards
    cards_col.update_many({"user_id": user_id}, {"$set": {"is_frozen": False}})

    # Unfreeze bank accounts
    bank_accounts_col.update_many({"user_id": user_id}, {"$set": {"is_frozen": False}})

    # Re-activate API keys
    api_keys_col.update_many({"user_id": user_id}, {"$set": {"is_active": True}})

    return {"status": "restored", "user_id": user_id, "email": user.get("email")}


@router.get("/{user_id}/status")
def lockdown_status(user_id: str):
    """Get lockdown status for a specific user."""
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user ID")

    user = users_col.find_one({"_id": oid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_cards = list(cards_col.find({"user_id": user_id}))
    user_keys = list(api_keys_col.find({"user_id": user_id}))
    user_accounts = list(bank_accounts_col.find({"user_id": user_id}))

    return {
        "user_id": user_id,
        "email": user.get("email"),
        "full_name": user.get("full_name"),
        "is_active": user.get("is_active", True),
        "is_locked": user.get("is_locked", False),
        "locked_at": user.get("locked_at").isoformat() if user.get("locked_at") else None,
        "cards": [{"number": c.get("card_number"), "type": c.get("card_type"), "is_frozen": c.get("is_frozen", False)} for c in user_cards],
        "bank_accounts": [{"iban": a.get("iban"), "balance": a.get("balance"), "is_frozen": a.get("is_frozen", False)} for a in user_accounts],
        "api_keys": [{"label": k.get("label"), "is_active": k.get("is_active", True)} for k in user_keys],
    }
