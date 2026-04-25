"""Campaign Generator — auto-creates phishing campaigns from OSINT scan results.

Takes scraped contact data and generates:
1. Campaign-ready CSV files
2. Auto-populated Campaign + Target DB records
3. Context-specific phishing templates per company/industry
"""

import csv
import io
import logging
from datetime import datetime
from typing import List, Dict, Optional

from backend.database import SessionLocal
from backend.models.osint_result import OsintScan, OsintResult
from backend.models.campaign import Campaign, CampaignMessage
from backend.models.target import Target

logger = logging.getLogger(__name__)

# ─── Phishing Template Library ───────────────────────────────
TEMPLATES = {
    "banking": {
        "subject": "🔒 Urgent: Verify Your Account — {{company}}",
        "body": """Dear {{name}},

We have detected unusual activity on your {{company}} account. For your security, we require you to verify your identity immediately.

Please click the link below to complete the verification process:

🔗 {{link}}

This link will expire in 24 hours. Failure to verify may result in temporary account suspension.

Best regards,
{{company}} Security Team
security@{{domain}}""",
    },
    "tech": {
        "subject": "⚠️ Action Required: SSO Session Expired — {{company}}",
        "body": """Hi {{name}},

Your Single Sign-On (SSO) session for {{company}} has expired. You need to re-authenticate to maintain access to your workspace and applications.

Re-authenticate here: {{link}}

If you did not request this, please contact IT support immediately.

— {{company}} IT Department""",
    },
    "corporate": {
        "subject": "📋 Mandatory: Annual Security Compliance Review — {{company}}",
        "body": """Dear {{name}},

As part of {{company}}'s annual security compliance program, all employees are required to complete the Security Awareness Assessment.

Complete your assessment: {{link}}

Deadline: End of business today.

This is mandatory per company policy. Non-compliance will be reported to your department head.

Regards,
{{company}} Compliance Team""",
    },
    "hr": {
        "subject": "📄 {{company}} — Updated Employment Agreement",
        "body": """Dear {{name}},

Please review and sign your updated employment agreement for {{company}}. This includes important changes to your benefits package.

Review document: {{link}}

Please complete this within 48 hours.

— {{company}} Human Resources""",
    },
    "generic": {
        "subject": "🔔 Important Notification from {{company}}",
        "body": """Dear {{name}},

You have a pending notification from {{company}} that requires your immediate attention.

View details: {{link}}

Please do not ignore this message.

Best regards,
{{company}} Administration""",
    },
}

# Domain keyword → template mapping
DOMAIN_TEMPLATE_MAP = {
    "bank": "banking", "ing": "banking", "bcr": "banking", "brd": "banking",
    "raiffeisen": "banking", "unicredit": "banking", "cec": "banking",
    "bt": "banking", "alpha": "banking", "garanti": "banking",
    "tech": "tech", "soft": "tech", "it": "tech", "dev": "tech",
    "digital": "tech", "cloud": "tech", "data": "tech", "ai": "tech",
}


def select_template(company: str, domain: str) -> Dict:
    """Select the best phishing template based on company/domain keywords."""
    lower = (company + " " + domain).lower()
    for keyword, template_key in DOMAIN_TEMPLATE_MAP.items():
        if keyword in lower:
            return TEMPLATES[template_key]
    return TEMPLATES["corporate"]


def generate_campaign_csv(scan_id: str) -> str:
    """Generate a CSV string from OSINT scan results."""
    db = SessionLocal()
    try:
        results = db.query(OsintResult).filter(
            OsintResult.scan_id == scan_id,
            OsintResult.email != "",
            OsintResult.email.isnot(None),
        ).order_by(OsintResult.risk_score.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "first_name", "last_name", "email", "phone",
            "company", "department", "risk_score", "confidence", "source",
        ])
        seen_emails = set()
        for r in results:
            if r.email and r.email not in seen_emails:
                seen_emails.add(r.email)
                writer.writerow([
                    r.first_name or "", r.last_name or "", r.email, r.phone or "",
                    r.company or "", r.department or "",
                    f"{r.risk_score:.2f}", f"{r.confidence:.2f}", r.source_url or "",
                ])

        return output.getvalue()
    finally:
        db.close()


def create_campaign_from_scan(
    scan_id: str,
    campaign_name: Optional[str] = None,
    channels: Optional[Dict[str, bool]] = None,
) -> Dict:
    """Auto-create a full campaign from OSINT scan results.

    Returns campaign dict with all targets populated.
    """
    db = SessionLocal()
    try:
        scan = db.query(OsintScan).filter(OsintScan.scan_id == scan_id).first()
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")

        results = db.query(OsintResult).filter(
            OsintResult.scan_id == scan_id,
            OsintResult.email != "",
            OsintResult.email.isnot(None),
        ).order_by(OsintResult.risk_score.desc()).all()

        if not results:
            raise ValueError("No email contacts found in scan results")

        # Deduplicate
        seen = set()
        unique_results = []
        for r in results:
            if r.email and r.email not in seen:
                seen.add(r.email)
                unique_results.append(r)

        # Select template
        template = select_template(scan.company_name, scan.domain)

        # Set default channels
        ch = channels or {"email": True}

        # Create campaign
        name = campaign_name or f"OSINT Auto — {scan.company_name} ({datetime.utcnow().strftime('%b %d %H:%M')})"
        campaign = Campaign(
            name=name,
            use_email=int(ch.get("email", True)),
            use_sms=int(ch.get("sms", False)),
            use_telegram=int(ch.get("telegram", False)),
            use_whatsapp=int(ch.get("whatsapp", False)),
            use_discord=int(ch.get("discord", False)),
            use_instagram=int(ch.get("instagram", False)),
            use_calendar=int(ch.get("calendar", False)),
            total_targets=len(unique_results),
        )
        db.add(campaign)
        db.flush()

        # Add message template
        msg = CampaignMessage(
            campaign_id=campaign.id,
            channel="email",
            subject=template["subject"],
            body=template["body"],
        )
        db.add(msg)

        # Add targets
        for r in unique_results:
            target = Target(
                campaign_id=campaign.id,
                first_name=r.first_name or "",
                last_name=r.last_name or "",
                email=r.email,
                phone=r.phone or "",
            )
            db.add(target)

        db.commit()
        db.refresh(campaign)

        logger.info(f"Campaign {campaign.id} auto-created from scan {scan_id}: "
                     f"{len(unique_results)} targets")

        return campaign.to_dict()

    finally:
        db.close()
