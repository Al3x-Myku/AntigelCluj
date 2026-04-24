"""Lockdown service — freeze all resources associated with a compromised account.

Uses the pluggable adapter system (lockdown_adapter.py) to integrate with
ANY existing user database: SQLite, PostgreSQL, MySQL, LDAP, or REST API.

Set LOCKDOWN_BACKEND in .env to choose: sqlite | postgresql | mysql | ldap | api
"""

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.account import Account, AuditLog
from backend.services.lockdown_adapter import get_adapter

logger = logging.getLogger(__name__)


def execute_lockdown(db: Session, account_id: int, triggered_by: str = "system") -> dict:
    """
    Execute full lockdown on an account using the configured adapter:
    1. Disable account login
    2. Revoke all active sessions
    3. Freeze all linked credentials/cards/tokens
    4. Log audit trail
    """
    adapter = get_adapter(db)

    # Check if account exists (via adapter or local DB)
    account_info = adapter.get_account_info(str(account_id))
    if not account_info:
        raise ValueError(f"Account {account_id} not found")

    actions = []
    now = datetime.utcnow()

    # 1. Disable account
    if adapter.disable_account(str(account_id)):
        actions.append("account_disabled")

    # 2. Revoke sessions
    session_count = adapter.revoke_sessions(str(account_id))
    actions.append(f"sessions_revoked:{session_count}")

    # 3. Freeze credentials
    cred_count = adapter.freeze_credentials(str(account_id))
    actions.append(f"credentials_frozen:{cred_count}")

    # 4. Audit log (always in local DB for PhishGuard's own tracking)
    try:
        audit = AuditLog(
            account_id=account_id,
            action="full_lockdown",
            details="; ".join(actions),
            triggered_by=triggered_by,
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass  # External DB might not have local audit table

    username = account_info.get("username", str(account_id))
    logger.warning(f"🔒 LOCKDOWN executed on {username} (ID: {account_id}): {actions}")

    return {
        "account_id": account_id,
        "username": username,
        "lockdown_at": now.isoformat(),
        "triggered_by": triggered_by,
        "actions": actions,
    }


def get_lockdown_status(db: Session, account_id: int) -> dict:
    """Get current lockdown status with resource tree."""
    adapter = get_adapter(db)
    info = adapter.get_account_info(str(account_id))
    if not info:
        raise ValueError(f"Account {account_id} not found")
    return info


def restore_account(db: Session, account_id: int, triggered_by: str = "operator") -> dict:
    """Restore a locked-down account."""
    adapter = get_adapter(db)

    if not adapter.restore_account(str(account_id)):
        raise ValueError(f"Failed to restore account {account_id}")

    # Audit log
    try:
        audit = AuditLog(
            account_id=account_id,
            action="account_restored",
            details="Account re-enabled. Cards/tokens remain in their current state.",
            triggered_by=triggered_by,
        )
        db.add(audit)
        db.commit()
    except Exception:
        pass

    logger.info(f"✅ Account {account_id} restored by {triggered_by}")
    return {"account_id": account_id, "status": "restored"}
