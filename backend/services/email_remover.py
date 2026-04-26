"""Email Remover — deletes flagged phishing emails from recipient mailboxes.

Supports two modes (set EMAIL_DEFENSE_MODE in .env):
  - 'local': Deletes .eml files from captured_emails/ directory (demo mode)
  - 'imap':  Connects via IMAP and deletes from real mailbox (production)
"""

import os
import logging
import imaplib
import email as email_mod
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Config
EMAIL_DEFENSE_MODE = os.getenv("EMAIL_DEFENSE_MODE", "local")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")
CAPTURED_DIR = Path(__file__).parent.parent.parent / "captured_emails"


def delete_email(
    message_id: str = "",
    subject: str = "",
    to_addr: str = "",
    source_file: str = "",
) -> dict:
    """
    Delete a phishing email from the recipient's mailbox.

    In local mode: removes the .eml file from captured_emails/.
    In IMAP mode: connects to the mailbox and deletes by Message-ID.

    Returns: {"success": bool, "method": str, "details": str}
    """
    if EMAIL_DEFENSE_MODE == "local":
        return _delete_local(message_id, subject, to_addr, source_file)
    elif EMAIL_DEFENSE_MODE == "imap":
        return _delete_imap(message_id, subject, to_addr)
    else:
        return {"success": False, "method": "unknown",
                "details": f"Unknown EMAIL_DEFENSE_MODE: {EMAIL_DEFENSE_MODE}"}


def _delete_local(message_id, subject, to_addr, source_file) -> dict:
    """Delete email from local captured_emails/ directory."""
    # If we have the exact source file path, use it
    if source_file and os.path.exists(source_file):
        try:
            os.remove(source_file)
            logger.info(f"🗑️ Deleted local email: {source_file}")
            return {"success": True, "method": "local_file",
                    "details": f"Deleted {os.path.basename(source_file)}"}
        except Exception as e:
            return {"success": False, "method": "local_file",
                    "details": f"Failed to delete {source_file}: {str(e)}"}

    # Otherwise search captured_emails/ for matching email
    if not CAPTURED_DIR.exists():
        return {"success": False, "method": "local_search",
                "details": "captured_emails/ directory not found"}

    deleted = []
    for eml_file in CAPTURED_DIR.glob("*.eml"):
        try:
            content = eml_file.read_text(errors="replace")
            match = False

            if message_id and message_id in content:
                match = True
            elif subject and subject in content:
                match = True
            elif to_addr and to_addr in content:
                # More specific: check Subject too
                if subject and subject.lower() in content.lower():
                    match = True

            if match:
                os.remove(eml_file)
                deleted.append(eml_file.name)
                logger.info(f"🗑️ Deleted local email: {eml_file.name}")
        except Exception as e:
            logger.error(f"Error scanning {eml_file}: {e}")

    if deleted:
        return {"success": True, "method": "local_search",
                "details": f"Deleted {len(deleted)} file(s): {', '.join(deleted)}"}
    return {"success": False, "method": "local_search",
            "details": "No matching email found in captured_emails/"}


def _delete_imap(message_id, subject, to_addr) -> dict:
    """Delete email from real mailbox via IMAP."""
    if not IMAP_USER or not IMAP_PASS:
        return {"success": False, "method": "imap",
                "details": "IMAP credentials not configured (set IMAP_USER/IMAP_PASS)"}

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("INBOX")

        # Search by Message-ID or Subject
        if message_id:
            status, data = mail.search(None, f'HEADER Message-ID "{message_id}"')
        elif subject:
            status, data = mail.search(None, f'SUBJECT "{subject}"')
        else:
            mail.logout()
            return {"success": False, "method": "imap",
                    "details": "No message_id or subject to search by"}

        if status != "OK" or not data[0]:
            mail.logout()
            return {"success": False, "method": "imap",
                    "details": "Email not found in mailbox"}

        msg_nums = data[0].split()
        deleted_count = 0
        for num in msg_nums:
            mail.store(num, '+FLAGS', '\\Deleted')
            deleted_count += 1

        mail.expunge()
        mail.logout()

        logger.info(f"🗑️ IMAP deleted {deleted_count} email(s) matching query")
        return {"success": True, "method": "imap",
                "details": f"Deleted {deleted_count} email(s) from {IMAP_USER}"}

    except Exception as e:
        logger.error(f"IMAP deletion failed: {e}")
        return {"success": False, "method": "imap",
                "details": f"IMAP error: {str(e)}"}


def scan_captured_emails_dir() -> list:
    """Scan all .eml files in captured_emails/ and return file info."""
    results = []
    if not CAPTURED_DIR.exists():
        return results

    for eml_file in sorted(CAPTURED_DIR.glob("*.eml")):
        try:
            content = eml_file.read_text(errors="replace")
            msg = email_mod.message_from_string(content)
            results.append({
                "filename": eml_file.name,
                "filepath": str(eml_file),
                "from": msg.get("From", ""),
                "to": msg.get("To", ""),
                "subject": msg.get("Subject", ""),
                "message_id": msg.get("Message-ID", ""),
                "date": msg.get("Date", ""),
                "size_bytes": eml_file.stat().st_size,
            })
        except Exception as e:
            logger.error(f"Error reading {eml_file}: {e}")

    return results
