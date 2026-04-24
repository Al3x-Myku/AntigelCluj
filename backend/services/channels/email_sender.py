"""Email sender — sends phishing emails via SMTP (Mailhog in dev)."""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
FROM_EMAIL = "security@securebank-verify.com"
FROM_NAME = "SecureBank Security Team"


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    """Send an email via SMTP (Mailhog in development)."""
    if not to_email:
        logger.warning("No email address provided")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg["To"] = to_email

        # Wrap plain body in minimal HTML if not already HTML
        if "<html" not in body_html.lower():
            html_body = f"""<!DOCTYPE html>
<html>
<head><style>
    body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
    .btn {{ display: inline-block; padding: 12px 30px; background: #1565c0;
            color: #fff; text-decoration: none; border-radius: 6px; font-weight: bold; }}
    .footer {{ color: #999; font-size: 12px; margin-top: 30px; }}
</style></head>
<body>
<div class="container">
{body_html}
</div>
</body>
</html>"""
        else:
            html_body = body_html

        # Also add plain text version
        plain_text = body_html.replace("<br>", "\n").replace("</p>", "\n")
        import re
        plain_text = re.sub(r"<[^>]+>", "", plain_text)

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.sendmail(FROM_EMAIL, to_email, msg.as_string())

        logger.info(f"Email sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Email failed to {to_email}: {e}")
        return False
