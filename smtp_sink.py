"""Ultra-light SMTP sink — captures all emails to ./captured_emails/"""

import os
import asyncio
import json
from datetime import datetime
from aiosmtpd.controller import Controller
from aiosmtpd.handlers import Message

CAPTURE_DIR = os.path.join(os.path.dirname(__file__), "captured_emails")
os.makedirs(CAPTURE_DIR, exist_ok=True)


class CaptureSMTP(Message):
    def handle_message(self, message):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        to = message.get("To", "unknown")
        safe_to = to.replace("@", "_at_").replace("<", "").replace(">", "").strip()
        fname = f"{ts}_{safe_to}.eml"
        fpath = os.path.join(CAPTURE_DIR, fname)

        with open(fpath, "w") as f:
            f.write(message.as_string())

        # Also log summary
        print(f"📨 Captured: {message.get('From')} → {to}")
        print(f"   Subject: {message.get('Subject')}")
        print(f"   Saved: {fname}")
        print()


if __name__ == "__main__":
    controller = Controller(CaptureSMTP(), hostname="0.0.0.0", port=1025)
    controller.start()
    print("🔧 SMTP Sink running on port 1025 — capturing all emails")
    print(f"   Saving to: {CAPTURE_DIR}/")
    print()
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()
