"""External Lockdown Service — Trigger lockdown across all registered mockup sites.

When PhishGuard detects an anomaly and triggers auto-lockdown, this module
calls into each external mockup site's lockdown API to freeze accounts
on those platforms too.

This is the KEY integration piece that connects PhishGuard's AI detection
engine to the real-world mockup applications.
"""

import os
import logging
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError
import json

logger = logging.getLogger(__name__)

# ─── Registered External Systems ─────────────────────────────
# These are the mockup sites that PhishGuard can lock down.
# Each entry has: name, base_url, type (for display), lockdown API prefix
EXTERNAL_SITES = [
    {
        "name": "SecurBank",
        "type": "Banking Platform (MongoDB)",
        "base_url": os.getenv("SECURBANK_URL", "http://localhost:9000"),
        "lockdown_prefix": "/api/lockdown",
    },
    {
        "name": "BreezeTech",
        "type": "IoT Startup (MySQL)",
        "base_url": os.getenv("BREEZETECH_URL", "http://localhost:9001"),
        "lockdown_prefix": "/api/lockdown",
    },
]

# ─── Cross-System Account Mapping ────────────────────────────
# Maps PhishGuard internal emails to the corresponding emails on
# each external platform. This is needed because users may have
# different emails on different services (realistic scenario).
#
# Format: phishguard_email -> {site_name: external_email}
ACCOUNT_MAP = {
    "victim1@phishguard.local": {
        "SecurBank": "andrei.popescu@gmail.com",
        "BreezeTech": "radu.gheorghe@gmail.com",
    },
    "victim2@phishguard.local": {
        "SecurBank": "maria.ionescu@yahoo.com",
        "BreezeTech": "alina.muresan@yahoo.com",
    },
}


def _resolve_email_for_site(email: str, site_name: str) -> str:
    """Resolve a PhishGuard email to the corresponding email on an external site."""
    mapping = ACCOUNT_MAP.get(email, {})
    return mapping.get(site_name, email)  # Fall back to same email if no mapping



def _http_get(url: str, timeout: int = 5) -> Optional[dict]:
    """Make a GET request and return JSON response."""
    try:
        req = Request(url)
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.debug(f"HTTP GET {url} failed: {e}")
        return None


def _http_post(url: str, timeout: int = 10) -> Optional[dict]:
    """Make a POST request and return JSON response."""
    try:
        req = Request(url, data=b"", method="POST")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.debug(f"HTTP POST {url} failed: {e}")
        return None


def check_site_health(site: dict) -> bool:
    """Check if an external site is reachable."""
    result = _http_get(f"{site['base_url']}/api/health")
    return result is not None and result.get("status") == "ok"


def find_user_on_site(site: dict, email: str) -> Optional[dict]:
    """Find a user on an external site by email address."""
    data = _http_get(f"{site['base_url']}{site['lockdown_prefix']}/users")
    if not data:
        return None
    for user in data.get("users", []):
        if user.get("email", "").lower() == email.lower():
            return user
    return None


def lockdown_on_site(site: dict, user_id: str) -> Optional[dict]:
    """Execute lockdown on a specific user on an external site."""
    return _http_post(f"{site['base_url']}{site['lockdown_prefix']}/{user_id}")


def restore_on_site(site: dict, user_id: str) -> Optional[dict]:
    """Restore a locked-down user on an external site."""
    return _http_post(f"{site['base_url']}{site['lockdown_prefix']}/{user_id}/restore")


def lockdown_external_sites(email: str) -> list[dict]:
    """Lock down a user across ALL external mockup sites by email.

    This is called by PhishGuard's auto-lockdown when an anomaly is detected.

    Returns a list of results from each site.
    """
    results = []

    for site in EXTERNAL_SITES:
        site_result = {
            "site": site["name"],
            "type": site["type"],
            "base_url": site["base_url"],
            "status": "skipped",
            "details": None,
        }

        # 1. Check if site is reachable
        if not check_site_health(site):
            site_result["status"] = "unreachable"
            logger.warning(f"⚠ {site['name']} unreachable at {site['base_url']}")
            results.append(site_result)
            continue

        # 2. Find user by email (with cross-system mapping)
        resolved_email = _resolve_email_for_site(email, site["name"])
        user = find_user_on_site(site, resolved_email)
        if not user:
            site_result["status"] = "user_not_found"
            logger.info(f"ℹ {site['name']}: no user with email {resolved_email} (mapped from {email})")
            results.append(site_result)
            continue

        user_id = user.get("id")

        # 3. Check if already locked
        if user.get("is_locked"):
            site_result["status"] = "already_locked"
            site_result["details"] = {"user_id": user_id, "email": email}
            results.append(site_result)
            continue

        # 4. Execute lockdown
        lockdown_result = lockdown_on_site(site, str(user_id))
        if lockdown_result and lockdown_result.get("status") == "locked":
            site_result["status"] = "locked"
            site_result["details"] = lockdown_result
            logger.warning(f"🔒 EXTERNAL LOCKDOWN on {site['name']}: {email} (user {user_id})")
        else:
            site_result["status"] = "failed"
            site_result["details"] = lockdown_result
            logger.error(f"❌ External lockdown FAILED on {site['name']}: {email}")

        results.append(site_result)

    return results


def restore_external_sites(email: str) -> list[dict]:
    """Restore a user across ALL external mockup sites by email."""
    results = []

    for site in EXTERNAL_SITES:
        site_result = {
            "site": site["name"],
            "status": "skipped",
        }

        if not check_site_health(site):
            site_result["status"] = "unreachable"
            results.append(site_result)
            continue

        resolved_email = _resolve_email_for_site(email, site["name"])
        user = find_user_on_site(site, resolved_email)
        if not user:
            site_result["status"] = "user_not_found"
            results.append(site_result)
            continue

        restore_result = restore_on_site(site, str(user.get("id")))
        if restore_result and restore_result.get("status") == "restored":
            site_result["status"] = "restored"
            logger.info(f"✅ EXTERNAL RESTORE on {site['name']}: {email}")
        else:
            site_result["status"] = "failed"

        results.append(site_result)

    return results


def get_external_status() -> list[dict]:
    """Get the health/status of all registered external systems."""
    statuses = []
    for site in EXTERNAL_SITES:
        online = check_site_health(site)
        statuses.append({
            "name": site["name"],
            "type": site["type"],
            "base_url": site["base_url"],
            "online": online,
        })
    return statuses
