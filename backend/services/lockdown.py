"""Lockdown service — freeze all resources associated with a compromised account."""

import logging
from datetime import datetime
from sqlalchemy.orm import Session

from backend.models.account import Account, Card, Session as SessionModel, Subscription, ApiToken, AuditLog

logger = logging.getLogger(__name__)


def execute_lockdown(db: Session, account_id: int, triggered_by: str = "system") -> dict:
    """
    Execute full lockdown on an account:
    1. Disable account login
    2. Revoke all active sessions
    3. Freeze all linked cards
    4. Revoke API/OAuth tokens
    5. Suspend subscriptions
    6. Log audit trail
    """
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} not found")

    actions = []
    now = datetime.utcnow()

    # 1. Disable account
    if account.is_active:
        account.is_active = False
        account.is_locked = True
        account.locked_at = now
        actions.append("account_disabled")

    # 2. Revoke sessions
    sessions = db.query(SessionModel).filter(
        SessionModel.account_id == account_id,
        SessionModel.status == "active"
    ).all()
    for s in sessions:
        s.status = "revoked"
        s.revoked_at = now
    actions.append(f"sessions_revoked:{len(sessions)}")

    # 3. Freeze cards
    cards = db.query(Card).filter(
        Card.account_id == account_id,
        Card.status == "active"
    ).all()
    for c in cards:
        c.status = "frozen"
        c.frozen_at = now
    actions.append(f"cards_frozen:{len(cards)}")

    # 4. Revoke API tokens
    tokens = db.query(ApiToken).filter(
        ApiToken.account_id == account_id,
        ApiToken.status == "active"
    ).all()
    for t in tokens:
        t.status = "revoked"
        t.revoked_at = now
    actions.append(f"tokens_revoked:{len(tokens)}")

    # 5. Suspend subscriptions
    subs = db.query(Subscription).filter(
        Subscription.account_id == account_id,
        Subscription.status == "active"
    ).all()
    for sub in subs:
        sub.status = "suspended"
        sub.suspended_at = now
    actions.append(f"subscriptions_suspended:{len(subs)}")

    # 6. Audit log
    audit = AuditLog(
        account_id=account_id,
        action="full_lockdown",
        details="; ".join(actions),
        triggered_by=triggered_by,
    )
    db.add(audit)
    db.commit()

    logger.warning(f"🔒 LOCKDOWN executed on account {account.username} (ID: {account_id}): {actions}")

    return {
        "account_id": account_id,
        "username": account.username,
        "lockdown_at": now.isoformat(),
        "triggered_by": triggered_by,
        "actions": actions,
    }


def get_lockdown_status(db: Session, account_id: int) -> dict:
    """Get current lockdown status with resource tree."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} not found")

    return account.to_dict(include_resources=True)


def restore_account(db: Session, account_id: int, triggered_by: str = "operator") -> dict:
    """Restore a locked-down account (re-enable, but don't unfreeze cards — manual step)."""
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise ValueError(f"Account {account_id} not found")

    account.is_active = True
    account.is_locked = False

    audit = AuditLog(
        account_id=account_id,
        action="account_restored",
        details="Account re-enabled by operator. Cards/tokens remain in their current state.",
        triggered_by=triggered_by,
    )
    db.add(audit)
    db.commit()

    logger.info(f"✅ Account {account.username} restored by {triggered_by}")
    return {"account_id": account_id, "status": "restored"}
