"""Email Scanner — phishing content analyzer for incoming emails.

Inspects email content for phishing indicators:
  - Urgency/financial keywords
  - URL analysis (mismatched links, shorteners, IP-based, homograph)
  - Header spoofing (From vs Reply-To mismatch, missing auth)
  - Dangerous attachments
  - Structural analysis (HTML vs text ratio, hidden elements)

Returns a structured verdict with score, risk level, and detailed flags.
"""

import re
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

URGENCY_KEYWORDS = {
    "urgent": 0.08, "immediately": 0.08, "expires": 0.07,
    "suspended": 0.09, "locked": 0.08, "verify your": 0.09,
    "confirm your identity": 0.10, "unusual activity": 0.10,
    "unauthorized": 0.09, "security alert": 0.08,
    "action required": 0.08, "final notice": 0.08,
    "your account": 0.05, "within 24 hours": 0.08,
    "within 48 hours": 0.07, "failure to": 0.07,
    "will be terminated": 0.09, "will be suspended": 0.09,
    "click here": 0.06, "click below": 0.06,
    "do not ignore": 0.07, "mandatory": 0.06,
    "compliance": 0.04, "re-authenticate": 0.08,
}

FINANCIAL_KEYWORDS = {
    "wire transfer": 0.12, "bank account": 0.08,
    "credit card": 0.07, "account number": 0.08,
    "routing number": 0.10, "payment": 0.05,
    "invoice": 0.05, "refund": 0.07,
    "bitcoin": 0.10, "cryptocurrency": 0.09,
    "gift card": 0.10, "prize": 0.08,
    "lottery": 0.12, "inheritance": 0.12,
    "beneficiary": 0.10,
}

URL_SHORTENERS = {
    "bit.ly", "goo.gl", "tinyurl.com", "t.co", "ow.ly",
    "is.gd", "buff.ly", "j.mp", "tiny.cc", "rb.gy", "cutt.ly",
    "shorte.st", "adf.ly", "clck.ru", "bl.ink", "shorturl.at",
    "rebrand.ly", "tr.im", "v.gd", "urlzs.com",
}

SUSPICIOUS_TLDS = {
    ".xyz", ".top", ".click", ".link", ".info", ".buzz",
    ".tk", ".ml", ".ga", ".cf", ".gq", ".work", ".date",
    ".review", ".download", ".racing", ".win", ".bid",
    ".loan", ".party", ".science", ".faith", ".accountant",
    ".trade", ".webcam", ".stream", ".cricket", ".space",
    ".icu", ".monster", ".rest", ".vip", ".cyou",
}

# Known legitimate CDN / tracking / analytics domains that are
# routinely embedded in transactional email but NOT phishing signals.
_CDN_WHITELIST = {
    "google.com", "googleapis.com", "gstatic.com",
    "microsoft.com", "microsoftonline.com", "live.com",
    "apple.com", "icloud.com",
    "amazon.com", "amazonaws.com", "awsstatic.com",
    "github.com", "githubusercontent.com",
    "cloudflare.com", "cloudfront.net",
    "sendgrid.net", "mailchimp.com", "mandrillapp.com",
    "mailgun.org",
    "stripe.com", "paypal.com",
    "linkedin.com", "twitter.com", "facebook.com",
    "youtube.com", "youtu.be",
    "w3.org", "schemas.microsoft.com",
}

# Brands commonly impersonated in phishing — used for subdomain squatting check.
_IMPERSONATED_BRANDS = {
    "paypal", "microsoft", "apple", "amazon", "google",
    "netflix", "chase", "wellsfargo", "bankofamerica",
    "citibank", "ing", "hsbc", "dhl", "fedex", "ups",
    "dropbox", "docusign", "adobe", "linkedin", "twitter",
    "facebook", "instagram", "ebay", "steam",
}

DANGEROUS_EXTENSIONS = {
    ".exe", ".scr", ".bat", ".cmd", ".com", ".pif",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".ps1", ".msi", ".hta", ".cpl", ".lnk", ".jar",
    ".docm", ".xlsm", ".pptm",
}

HOMOGRAPH_MAP = {
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p',
    '\u0441': 'c', '\u0443': 'y', '\u0445': 'x', '\u0456': 'i',
}


@dataclass
class ScanVerdict:
    score: float = 0.0
    risk_level: str = "safe"
    flags: List[str] = field(default_factory=list)
    recommendation: str = ""
    details: Dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class EmailScanner:
    SUSPICIOUS_THRESHOLD = 0.30
    DANGEROUS_THRESHOLD = 0.60

    def scan(self, subject="", body="", from_addr="", to_addr="",
             reply_to="", headers=None, attachments=None) -> ScanVerdict:
        verdict = ScanVerdict()
        headers = headers or {}
        attachments = attachments or []
        full_text = f"{subject} {body}".lower()
        score = 0.0

        # 1. Urgency keywords
        urgency_hits = [k for k in URGENCY_KEYWORDS if k in full_text]
        for k in urgency_hits:
            score += URGENCY_KEYWORDS[k]
        if urgency_hits:
            verdict.flags.append(f"Urgency keywords: {', '.join(urgency_hits[:5])}")
        if len(urgency_hits) >= 3:
            score += 0.05
            verdict.flags.append("Multiple urgency keywords (keyword stacking)")

        # 2. Financial keywords
        financial_hits = [k for k in FINANCIAL_KEYWORDS if k in full_text]
        for k in financial_hits:
            score += FINANCIAL_KEYWORDS[k]
        if financial_hits:
            verdict.flags.append(f"Financial lure keywords: {', '.join(financial_hits[:5])}")

        # 3. URL analysis — score is accumulated per-signal inside _analyze_urls()
        urls = re.findall(r'https?://[^\s<>"\']+', body + " " + subject)
        self._last_url_score = 0.0  # reset before call
        url_flags = self._analyze_urls(urls, body, from_addr)
        verdict.flags.extend(url_flags)
        score += self._last_url_score  # use fine-grained per-signal weights, not flat 0.06

        # 4. Header spoofing
        header_flags = self._analyze_headers(from_addr, reply_to, to_addr, headers)
        verdict.flags.extend(header_flags)
        score += len(header_flags) * 0.08

        # 5. Attachments
        attach_flags = self._analyze_attachments(attachments)
        verdict.flags.extend(attach_flags)
        score += len(attach_flags) * 0.12

        # 6. Structure
        struct_flags = self._analyze_structure(body, subject)
        verdict.flags.extend(struct_flags)
        score += len(struct_flags) * 0.04

        # 7. Homographs
        for char in (subject + " " + from_addr):
            if char in HOMOGRAPH_MAP:
                verdict.flags.append(f"Unicode homograph: '{char}' looks like '{HOMOGRAPH_MAP[char]}'")
                score += 0.15
                break

        # Finalize
        verdict.score = min(1.0, round(score, 4))
        if verdict.score >= self.DANGEROUS_THRESHOLD:
            verdict.risk_level = "dangerous"
            verdict.recommendation = "DELETE — High-confidence phishing. Remove immediately."
        elif verdict.score >= self.SUSPICIOUS_THRESHOLD:
            verdict.risk_level = "suspicious"
            verdict.recommendation = "QUARANTINE — Flag for manual review."
        else:
            verdict.risk_level = "safe"
            verdict.recommendation = "ALLOW — No significant phishing indicators."

        verdict.details = {
            "urgency_hits": len(urgency_hits),
            "financial_hits": len(financial_hits),
            "urls_found": len(urls),
            "total_flags": len(verdict.flags),
        }
        return verdict

    # ── URL weight constants (per-signal, additive) ─────────────────────────
    _W_IP_URL        = 0.20  # IP-literal address — very high phishing signal
    _W_SHORTENER     = 0.15  # Link shortener hides final destination
    _W_SUSP_TLD      = 0.10  # Abused free/exotic TLD
    _W_PUNYCODE      = 0.18  # xn-- internationalized domain (homograph)
    _W_SUBDOMAIN_SQT = 0.18  # Brand in subdomain, alien apex domain
    _W_AT_IN_URL     = 0.20  # @ in URL — RFC trick to disguise real host
    _W_DATA_URI      = 0.25  # data: URI — near-certain payload smuggling
    _W_OPEN_REDIRECT = 0.15  # Redirect param in URL pointing elsewhere
    _W_EXCESS_SUB    = 0.08  # Deeply nested subdomains
    _W_RANDOM_DOMAIN = 0.12  # Domain looks algorithmically generated
    _W_SENDER_MISMATCH = 0.07  # URL apex ≠ sender domain (with CDN whitelist)
    _W_MISMATCH_LINK = 0.18  # Anchor text domain ≠ href domain

    @staticmethod
    def _decode_html_entities(text: str) -> str:
        """Minimal HTML-entity decode so &#58; or &#x2F; don't bypass URL regex."""
        text = re.sub(r'&#x([0-9a-fA-F]+);', lambda m: chr(int(m.group(1), 16)), text)
        text = re.sub(r'&#([0-9]+);', lambda m: chr(int(m.group(1))), text)
        return text

    @staticmethod
    def _strip_port(netloc: str) -> str:
        """Return netloc with port removed: 'evil.com:8080' → 'evil.com'."""
        # IPv6 literal: [::1]:8080
        if netloc.startswith("["):
            return netloc.split("]")[0] + "]"
        return netloc.split(":")[0]

    @staticmethod
    def _base_domain(host: str) -> str:
        """Return apex domain (last two labels): 'a.b.evil.com' → 'evil.com'."""
        parts = host.split(".")
        return ".".join(parts[-2:]) if len(parts) >= 2 else host

    @staticmethod
    def _looks_random(domain: str) -> bool:
        """Heuristic: domain label with high consonant-cluster density looks DGA-generated."""
        label = domain.split(".")[0]  # check the leftmost label
        if len(label) < 8:
            return False
        vowels = sum(1 for c in label if c in "aeiou")
        consonant_ratio = 1 - (vowels / max(len(label), 1))
        # >75 % consonants AND no recognisable brand → likely DGA
        return consonant_ratio > 0.75

    def _analyze_urls(self, urls, body, from_addr):
        """Analyse extracted URLs for phishing indicators.

        Each detected signal appends a flag and contributes its weighted score
        to the caller (via len(flags) * per-flag-weight is replaced below with
        per-signal weights returned as a separate float).
        """
        flags = []
        url_score = 0.0
        from_domain = from_addr.split("@")[-1].lower() if "@" in from_addr else ""
        from_apex = self._base_domain(from_domain) if from_domain else ""

        # ── Decode HTML entities in body before URL extraction ────────────────
        decoded_body = self._decode_html_entities(body)

        # ── Re-extract after decode so entity-smuggled URLs are caught ────────
        extra_urls = re.findall(r'https?://[^\s<>"\' ]+', decoded_body)
        all_urls = list(dict.fromkeys(urls + extra_urls))  # deduplicate, preserve order

        # ── data: URI check (before urlparse loop — different scheme) ─────────
        data_uri_pat = re.compile(r'data:\s*text/html', re.IGNORECASE)
        if data_uri_pat.search(body) or data_uri_pat.search(decoded_body):
            flags.append("data: URI detected — possible HTML payload smuggling")
            url_score += self._W_DATA_URI

        for url in all_urls[:20]:  # raised cap: 20
            try:
                parsed = urlparse(url)
                raw_netloc = parsed.netloc.lower()
                host = self._strip_port(raw_netloc)  # BUG FIX: strip port before all checks
                base = self._base_domain(host)        # BUG FIX: computed from port-stripped host

                # ── 1. IP-literal URL ────────────────────────────────────────
                # BUG FIX: anchored with $ so 1.2.3.4.evil.com is NOT matched
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', host):
                    flags.append(f"IP-based URL (no domain name): {url[:80]}")
                    url_score += self._W_IP_URL
                    continue  # remaining checks not meaningful for bare IP

                # ── 2. IPv6 literal ──────────────────────────────────────────
                if host.startswith("["):
                    flags.append(f"IPv6-literal URL: {url[:80]}")
                    url_score += self._W_IP_URL
                    continue

                # ── 3. Punycode / IDN homograph ──────────────────────────────
                if "xn--" in host:
                    flags.append(f"Punycode/IDN domain (homograph risk): {host}")
                    url_score += self._W_PUNYCODE

                # ── 4. URL shortener ─────────────────────────────────────────
                # BUG FIX: check base (port-stripped) not raw domain
                if base in URL_SHORTENERS:
                    flags.append(f"URL shortener hides destination: {base}")
                    url_score += self._W_SHORTENER

                # ── 5. Suspicious TLD ────────────────────────────────────────
                # BUG FIX: skip if already flagged as shortener to avoid double-flag
                elif any(host.endswith(tld) for tld in SUSPICIOUS_TLDS):
                    flags.append(f"Suspicious/abused TLD: {host}")
                    url_score += self._W_SUSP_TLD

                # ── 6. Subdomain brand squatting ─────────────────────────────
                # e.g. paypal.com.attacker.net — brand in subdomain, alien apex
                subdomains = host.split(".")[:-2]  # labels before the apex
                for brand in _IMPERSONATED_BRANDS:
                    if any(brand in label for label in subdomains) and brand not in base:
                        flags.append(
                            f"Subdomain brand squatting: '{brand}' in subdomain of '{base}'"
                        )
                        url_score += self._W_SUBDOMAIN_SQT
                        break

                # ── 7. Excessive subdomain depth (≥ 4 labels) ────────────────
                if host.count(".") >= 4:
                    flags.append(f"Excessive subdomain depth: {host}")
                    url_score += self._W_EXCESS_SUB

                # ── 8. @ symbol in URL (RFC-allowed but classic phishing) ─────
                if "@" in url:
                    flags.append(f"@ in URL (credential confusion trick): {url[:80]}")
                    url_score += self._W_AT_IN_URL

                # ── 9. Open redirect pattern ──────────────────────────────────
                redirect_pat = re.compile(
                    r'[?&](url|redirect|redir|next|goto|target|link|dest)=https?://',
                    re.IGNORECASE
                )
                if redirect_pat.search(url):
                    flags.append(f"Open redirect parameter in URL: {url[:80]}")
                    url_score += self._W_OPEN_REDIRECT

                # ── 10. DGA / random-string domain heuristic ─────────────────
                if self._looks_random(base.split(".")[0]):
                    flags.append(f"Domain appears algorithmically generated: {base}")
                    url_score += self._W_RANDOM_DOMAIN

                # ── 11. Sender-domain mismatch (whitelist-aware) ──────────────
                # BUG FIX: only fire when URL looks credential-related AND
                # apex is not in CDN whitelist — avoids false-positive flood
                credential_path = re.search(
                    r'/(login|signin|verify|auth|account|secure|update|confirm)',
                    parsed.path, re.IGNORECASE
                )
                if (
                    from_apex
                    and base != from_apex
                    and base not in _CDN_WHITELIST
                    and credential_path
                ):
                    flags.append(
                        f"Credential URL domain '{base}' differs from sender '{from_apex}'"
                    )
                    url_score += self._W_SENDER_MISMATCH

            except Exception:
                continue

        # ── Mismatched anchor text vs href ────────────────────────────────────
        href_pat = re.compile(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', re.IGNORECASE
        )
        for href, text in href_pat.findall(decoded_body):
            tc = text.strip().lower()
            if re.match(r'https?://', tc) or ("." in tc and " " not in tc):
                if href.startswith("http"):
                    href_host = self._strip_port(urlparse(href).netloc.lower())
                    href_apex = self._base_domain(href_host)
                else:
                    href_apex = ""
                if tc.startswith("http"):
                    text_apex = self._base_domain(
                        self._strip_port(urlparse(tc).netloc.lower())
                    )
                else:
                    text_apex = self._base_domain(tc.split("/")[0])
                # BUG FIX: compare apex domains, not raw netloc (port/www mismatches)
                if href_apex and text_apex and href_apex != text_apex:
                    flags.append(
                        f"Mismatched link text/href: shows '{tc[:50]}' → '{href[:50]}'"
                    )
                    url_score += self._W_MISMATCH_LINK

        # Store weighted URL score for caller
        self._last_url_score = url_score
        return flags

    def _analyze_headers(self, from_addr, reply_to, to_addr, headers):
        flags = []
        if reply_to and from_addr:
            fd = from_addr.split("@")[-1].lower() if "@" in from_addr else ""
            rd = reply_to.split("@")[-1].lower() if "@" in reply_to else ""
            if fd and rd and fd != rd:
                flags.append(f"Reply-To ({rd}) differs from From ({fd})")
        freemail = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "protonmail.com"}
        fd = from_addr.split("@")[-1].lower() if "@" in from_addr else ""
        fn = from_addr.split("@")[0].lower() if "@" in from_addr else ""
        corp_words = {"bank", "security", "admin", "support", "helpdesk", "finance"}
        if fd in freemail and any(w in fn for w in corp_words):
            flags.append(f"Corporate-looking sender using freemail ({fd})")
        return flags

    def _analyze_attachments(self, attachments):
        flags = []
        for fn in attachments:
            lower = fn.lower()
            for ext in DANGEROUS_EXTENSIONS:
                if lower.endswith(ext):
                    flags.append(f"Dangerous attachment: {fn}")
                    break
            parts = lower.rsplit(".", 2)
            if len(parts) >= 3 and f".{parts[-1]}" in DANGEROUS_EXTENSIONS:
                flags.append(f"Double extension trick: {fn}")
        return flags

    def _analyze_structure(self, body, subject):
        flags = []
        if subject and subject.upper() == subject and len(subject) > 10:
            flags.append("Subject is ALL CAPS (intimidation)")
        if re.search(r'display\s*:\s*none', body, re.IGNORECASE):
            flags.append("Hidden elements (display:none)")
        body_lower = body.lower()
        brands = [(r'\bpaypal\b', "PayPal"), (r'\bmicrosoft\b', "Microsoft"),
                   (r'\bapple\s*id\b', "Apple"), (r'\bamazon\b', "Amazon"),
                   (r'\bnetflix\b', "Netflix"), (r'\bING\b', "ING Bank")]
        for pat, brand in brands:
            if re.search(pat, body_lower):
                flags.append(f"Brand impersonation: {brand}")
                break
        if re.search(r'dear\s+(customer|user|account\s*holder|sir|madam|valued)', body_lower):
            flags.append("Generic greeting (not personalized)")
        return flags


_scanner = EmailScanner()


def scan_email(subject="", body="", from_addr="", to_addr="",
               reply_to="", headers=None, attachments=None) -> ScanVerdict:
    return _scanner.scan(subject=subject, body=body, from_addr=from_addr,
                         to_addr=to_addr, reply_to=reply_to,
                         headers=headers, attachments=attachments)


def scan_raw_eml(eml_content: str) -> ScanVerdict:
    import email as email_mod
    from email import policy
    msg = email_mod.message_from_string(eml_content, policy=policy.default)
    subject = msg.get("Subject", "")
    from_addr = msg.get("From", "")
    to_addr = msg.get("To", "")
    reply_to = msg.get("Reply-To", "")
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() in ("text/plain", "text/html"):
                try:
                    body += part.get_content() + "\n"
                except Exception:
                    try:
                        body += part.get_payload(decode=True).decode("utf-8", errors="replace") + "\n"
                    except Exception:
                        pass
    else:
        try:
            body = msg.get_content()
        except Exception:
            try:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")
            except Exception:
                body = str(msg.get_payload())
    headers = {k: v for k, v in msg.items()}
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            fn = part.get_filename()
            if fn:
                attachments.append(fn)
    return scan_email(subject=subject, body=body, from_addr=from_addr,
                      to_addr=to_addr, reply_to=reply_to,
                      headers=headers, attachments=attachments)
