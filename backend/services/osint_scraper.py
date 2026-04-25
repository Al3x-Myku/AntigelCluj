"""OSINT Scraper — autonomous web reconnaissance for emails and phones.

Scrapes public company pages, directories, and search-indexed content
to discover contact information (emails, phone numbers) for phishing campaign targeting.
"""

import re
import time
import random
import logging
import threading
from datetime import datetime
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from backend.database import SessionLocal
from backend.models.osint_result import OsintScan, OsintResult

logger = logging.getLogger(__name__)

# ─── Config ──────────────────────────────────────────────────
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

PHONE_REGEX = re.compile(
    r"""(?:(?:\+|00)?\s*(?:4[0-9]|3[3-9]|4[4-9]|1)\s*)?"""  # Country code
    r"""(?:\(?\d{2,4}\)?[\s.\-]?)"""     # Area code
    r"""(?:\d[\s.\-]?){5,9}\d""",        # Number
    re.VERBOSE,
)

ROMANIAN_MOBILE = re.compile(r"(?:\+?40|0)\s*7\d{8}")

# Pages likely to contain contact info
CONTACT_PATHS = [
    "/contact", "/contacts", "/about", "/about-us", "/team", "/our-team",
    "/people", "/staff", "/leadership", "/management", "/directory",
    "/contact-us", "/contacte", "/echipa", "/despre", "/despre-noi",
    "/impressum", "/imprint", "/privacy", "/legal",
]

DEPARTMENT_KEYWORDS = {
    "hr": "Human Resources", "human resources": "Human Resources",
    "finance": "Finance", "accounting": "Finance",
    "it": "IT", "tech": "IT", "engineering": "IT", "development": "IT",
    "marketing": "Marketing", "sales": "Sales", "commercial": "Sales",
    "legal": "Legal", "compliance": "Legal",
    "support": "Support", "customer": "Support",
    "ceo": "Executive", "cto": "Executive", "cfo": "Executive",
    "director": "Executive", "manager": "Management",
    "admin": "Administration", "office": "Administration",
    "security": "Security", "infosec": "Security",
}

ROLE_RISK_MAP = {
    "Executive": 0.95, "Management": 0.85, "Finance": 0.90,
    "IT": 0.80, "Security": 0.75, "Human Resources": 0.70,
    "Legal": 0.65, "Sales": 0.60, "Marketing": 0.55,
    "Support": 0.50, "Administration": 0.45,
}

# Domains to skip (common false positives)
SKIP_DOMAINS = {
    "example.com", "sentry.io", "w3.org", "schema.org", "facebook.com",
    "twitter.com", "instagram.com", "youtube.com", "google.com",
    "googleapis.com", "gstatic.com", "cloudflare.com", "jsdelivr.net",
    "bootstrapcdn.com", "jquery.com", "fontawesome.com", "wordpress.org",
    "wp.com", "gravatar.com", "github.com", "linkedin.com",
}


class OsintScanner:
    """Autonomous OSINT scanner that discovers emails and phones from public sources."""

    def __init__(self, domain: str, company_name: str = "", scan_id: str = ""):
        self.domain = domain.lower().strip()
        self.company_name = company_name or self.domain.split(".")[0].title()
        self.scan_id = scan_id
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ro;q=0.8",
        })
        self.session.verify = False
        self.found_emails: Set[str] = set()
        self.found_phones: Set[str] = set()
        self.results: List[Dict] = []
        self.log_lines: List[str] = []
        self._visited_urls: Set[str] = set()

    def _log(self, message: str):
        ts = datetime.utcnow().strftime("%H:%M:%S")
        line = f"[{ts}] {message}"
        self.log_lines.append(line)
        logger.info(f"[OSINT:{self.scan_id[:8]}] {message}")

    def _delay(self):
        time.sleep(random.uniform(0.3, 1.2))

    def _fetch(self, url: str, timeout: int = 10) -> Optional[str]:
        if url in self._visited_urls:
            return None
        self._visited_urls.add(url)
        try:
            self.session.headers["User-Agent"] = random.choice(USER_AGENTS)
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200 and "text" in resp.headers.get("content-type", ""):
                return resp.text
            else:
                self._log(f"  ↳ HTTP {resp.status_code} for {url}")
        except requests.RequestException as e:
            self._log(f"  ↳ Error fetching {url}: {str(e)[:80]}")
        return None

    def _extract_emails(self, text: str, source_url: str) -> List[str]:
        raw = EMAIL_REGEX.findall(text)
        valid = []
        for email in raw:
            email = email.lower().strip().rstrip(".")
            email_domain = email.split("@")[1] if "@" in email else ""
            if email_domain in SKIP_DOMAINS:
                continue
            if email.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js")):
                continue
            if len(email) > 100:
                continue
            if email not in self.found_emails:
                self.found_emails.add(email)
                valid.append(email)
        return valid

    def _extract_phones(self, text: str) -> List[str]:
        phones = set()
        for match in PHONE_REGEX.finditer(text):
            phone = re.sub(r"[\s.\-()]", "", match.group())
            if len(phone) >= 8 and phone not in self.found_phones:
                self.found_phones.add(phone)
                phones.add(phone)
        for match in ROMANIAN_MOBILE.finditer(text):
            phone = re.sub(r"[\s.\-()]", "", match.group())
            if phone not in self.found_phones:
                self.found_phones.add(phone)
                phones.add(phone)
        return list(phones)

    def _guess_name_from_email(self, email: str) -> tuple:
        local = email.split("@")[0]
        local = re.sub(r"[0-9]+$", "", local)
        separators = [".", "_", "-"]
        for sep in separators:
            if sep in local:
                parts = local.split(sep)
                if len(parts) >= 2:
                    return parts[0].title(), parts[-1].title()
        if len(local) > 2:
            return local.title(), ""
        return "", ""

    def _guess_department(self, text: str, email: str) -> str:
        text_lower = (text + " " + email).lower()
        for keyword, dept in DEPARTMENT_KEYWORDS.items():
            if keyword in text_lower:
                return dept
        return "General"

    def _build_result(self, email: str = "", phone: str = "",
                      source_url: str = "", context_text: str = "") -> Dict:
        first, last = ("", "")
        if email:
            first, last = self._guess_name_from_email(email)
        dept = self._guess_department(context_text, email)
        risk = ROLE_RISK_MAP.get(dept, 0.50)
        email_domain = email.split("@")[1] if "@" in email else self.domain
        is_target_domain = self.domain in email_domain
        confidence = 0.90 if is_target_domain else 0.50

        return {
            "email": email,
            "phone": phone,
            "first_name": first,
            "last_name": last,
            "company": self.company_name,
            "domain": email_domain if email else self.domain,
            "department": dept,
            "role": dept,
            "source_url": source_url,
            "confidence": confidence,
            "risk_score": risk,
        }

    # ─── Scraping Strategies ─────────────────────────────────

    def scan_main_site(self):
        """Scrape the target domain's main pages."""
        self._log(f"🌐 Scanning main site: {self.domain}")
        base = f"https://{self.domain}"

        html = self._fetch(base)
        if not html:
            base = f"http://{self.domain}"
            html = self._fetch(base)
        if not html:
            self._log(f"  ✗ Could not reach {self.domain}")
            return

        self._log(f"  ✓ Main page loaded")
        self._process_page(html, base)
        self._delay()

        # Crawl contact/about pages
        for path in CONTACT_PATHS:
            url = urljoin(base, path)
            html = self._fetch(url)
            if html:
                self._log(f"  ✓ Found page: {path}")
                self._process_page(html, url)
                self._delay()

    def scan_directory_buster(self):
        """Multi-threaded GoBuster-style path discovery."""
        import concurrent.futures
        self._log(f"🚀 Launching fast directory buster for {self.domain}")
        
        # Extended payload list representing common sensitive/business endpoints
        payloads = [
            "/admin", "/login", "/dashboard", "/portal", "/staff",
            "/employee", "/intranet", "/documents", "/uploads", "/files",
            "/assets", "/investors", "/media", "/press-releases",
            "/about.pdf", "/company.pdf", "/profile.pdf", "/team.pdf",
            "/contact.pdf", "/directory.pdf", "/roster.pdf",
            "/sitemap.xml", "/robots.txt", "/api", "/api/v1/users",
            "/hr", "/careers", "/jobs", "/board", "/executives"
        ]
        
        base = f"https://{self.domain}"
        
        def _test_path(path: str):
            url = urljoin(base, path)
            try:
                # Use a fast timeout for fuzzing
                resp = self.session.get(url, timeout=5, allow_redirects=True)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "").lower()
                    if "text" in content_type or "json" in content_type:
                        return url, resp.text
                    # Note: downloading/parsing PDFs is complex without external libs
                    # We will log the finding but parsing is best-effort via raw text extraction
                    elif "pdf" in content_type:
                        return url, f"PDF file discovered: {url}" 
            except requests.RequestException:
                pass
            return url, None

        discovered_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_path = {executor.submit(_test_path, path): path for path in payloads}
            for future in concurrent.futures.as_completed(future_to_path):
                url, content = future.result()
                if content:
                    discovered_count += 1
                    self._log(f"  ✓ Discovered: {urlparse(url).path}")
                    if "PDF file" not in content:
                        self._process_page(content, url)
                        
        self._log(f"  ✓ Directory buster complete: {discovered_count} paths found.")



    def scan_google_dorks(self):
        """Search Google for indexed emails/pages from the target domain."""
        self._log(f"🔍 Running Google dork searches for {self.domain}")
        dorks = [
            f'"@{self.domain}" email',
            f'site:{self.domain} contact email',
            f'site:{self.domain} team OR staff OR about',
            f'"{self.company_name}" email contact',
            f'"{self.domain}" filetype:pdf',
        ]
        for dork in dorks:
            self._delay()
            try:
                url = f"https://www.google.com/search?q={requests.utils.quote(dork)}&num=20"
                html = self._fetch(url, timeout=8)
                if html:
                    self._log(f"  ✓ Google results for: {dork[:50]}...")
                    soup = BeautifulSoup(html, "lxml")
                    text = soup.get_text(" ", strip=True)
                    emails = self._extract_emails(text, url)
                    if emails:
                        self._log(f"    Found {len(emails)} emails")
                        for email in emails:
                            self.results.append(self._build_result(email=email, source_url="Google Search", context_text=text[:500]))
                    # Extract linked URLs to crawl
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if self.domain in href and href.startswith("http"):
                            parsed = urlparse(href)
                            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
                            if clean not in self._visited_urls:
                                page_html = self._fetch(clean)
                                if page_html:
                                    self._process_page(page_html, clean)
                                    self._delay()
                else:
                    self._log(f"  ✗ No results for: {dork[:50]}...")
            except Exception as e:
                self._log(f"  ✗ Dork error: {str(e)[:60]}")

    def scan_public_directories(self):
        """Check public business directories for contact info."""
        self._log(f"📂 Scanning public directories")
        directories = [
            f"https://www.listafirme.ro/search?q={requests.utils.quote(self.company_name)}",
            f"https://www.risco.ro/cautare?query={requests.utils.quote(self.company_name)}",
            f"https://www.europages.co.uk/search?q={requests.utils.quote(self.company_name)}",
            f"https://opencorporates.com/companies?q={requests.utils.quote(self.company_name)}&jurisdiction_code=ro",
        ]
        for dir_url in directories:
            self._delay()
            html = self._fetch(dir_url, timeout=8)
            if html:
                self._log(f"  ✓ Directory hit: {urlparse(dir_url).netloc}")
                self._process_page(html, dir_url)

    def scan_email_patterns(self):
        """Generate likely email patterns from commonly used formats."""
        self._log(f"🧩 Generating email pattern permutations for @{self.domain}")
        common_prefixes = [
            "contact", "info", "office", "hello", "support", "sales",
            "marketing", "hr", "jobs", "careers", "admin", "press",
            "media", "legal", "compliance", "security", "it",
            "help", "feedback", "general", "reception",
        ]
        for prefix in common_prefixes:
            email = f"{prefix}@{self.domain}"
            if email not in self.found_emails:
                self.found_emails.add(email)
                dept = self._guess_department(prefix, email)
                self.results.append({
                    "email": email,
                    "phone": "",
                    "first_name": "",
                    "last_name": "",
                    "company": self.company_name,
                    "domain": self.domain,
                    "department": dept,
                    "role": dept,
                    "source_url": "Pattern Inference",
                    "confidence": 0.40,
                    "risk_score": ROLE_RISK_MAP.get(dept, 0.30),
                })
        self._log(f"  ✓ Generated {len(common_prefixes)} pattern-based emails")

    def scan_social_media(self):
        """Try to extract info from public social profiles/pages."""
        self._log(f"📱 Checking social media presence")
        social_urls = [
            f"https://www.linkedin.com/company/{self.domain.split('.')[0]}/about/",
            f"https://www.facebook.com/{self.domain.split('.')[0]}/about",
            f"https://twitter.com/{self.domain.split('.')[0]}",
        ]
        for url in social_urls:
            self._delay()
            html = self._fetch(url, timeout=8)
            if html:
                self._log(f"  ✓ Social page: {urlparse(url).netloc}")
                self._process_page(html, url)

    def _process_page(self, html: str, source_url: str):
        """Extract emails and phones from raw HTML."""
        try:
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
        except Exception:
            text = html

        emails = self._extract_emails(text, source_url)
        phones = self._extract_phones(text)

        for email in emails:
            self.results.append(self._build_result(
                email=email, source_url=source_url, context_text=text[:1000]
            ))
        for phone in phones:
            if not any(r.get("phone") == phone for r in self.results):
                self.results.append(self._build_result(
                    phone=phone, source_url=source_url, context_text=text[:1000]
                ))

    # ─── Main Entry Point ────────────────────────────────────

    def run(self) -> Dict:
        """Execute full OSINT scan. Returns summary dict."""
        start = time.time()
        self._log(f"═══ OSINT RECON STARTED: {self.company_name} ({self.domain}) ═══")

        try:
            self.scan_main_site()
            self.scan_directory_buster()
            self.scan_google_dorks()
            self.scan_public_directories()
            self.scan_email_patterns()
            self.scan_social_media()
        except Exception as e:
            self._log(f"✗ Scan error: {str(e)}")

        duration = time.time() - start
        self._log(f"═══ SCAN COMPLETE in {duration:.1f}s — "
                   f"{len(self.found_emails)} emails, {len(self.found_phones)} phones ═══")

        return {
            "scan_id": self.scan_id,
            "domain": self.domain,
            "company_name": self.company_name,
            "total_emails": len(self.found_emails),
            "total_phones": len(self.found_phones),
            "total_contacts": len(self.results),
            "duration_seconds": duration,
            "results": self.results,
            "log": "\n".join(self.log_lines),
        }


# ─── Background Runner ──────────────────────────────────────

def run_osint_scan_background(scan_id: str, domain: str, company_name: str):
    """Run OSINT scan in background thread and save results to DB."""
    import warnings
    warnings.filterwarnings("ignore", message="Unverified HTTPS request")

    db = SessionLocal()
    try:
        scanner = OsintScanner(domain=domain, company_name=company_name, scan_id=scan_id)
        result = scanner.run()

        # Save results
        scan = db.query(OsintScan).filter(OsintScan.scan_id == scan_id).first()
        if scan:
            scan.status = "completed"
            scan.total_emails = result["total_emails"]
            scan.total_phones = result["total_phones"]
            scan.total_contacts = result["total_contacts"]
            scan.duration_seconds = result["duration_seconds"]
            scan.completed_at = datetime.utcnow()
            scan.log = result["log"]

            for r in result["results"]:
                osint_result = OsintResult(
                    scan_id=scan_id,
                    email=r.get("email", ""),
                    phone=r.get("phone", ""),
                    first_name=r.get("first_name", ""),
                    last_name=r.get("last_name", ""),
                    company=r.get("company", ""),
                    domain=r.get("domain", ""),
                    department=r.get("department", ""),
                    role=r.get("role", ""),
                    source_url=r.get("source_url", ""),
                    confidence=r.get("confidence", 0.5),
                    risk_score=r.get("risk_score", 0.5),
                )
                db.add(osint_result)
            db.commit()
            logger.info(f"OSINT scan {scan_id} saved: {result['total_contacts']} contacts")

    except Exception as e:
        logger.error(f"OSINT scan {scan_id} failed: {e}")
        scan = db.query(OsintScan).filter(OsintScan.scan_id == scan_id).first()
        if scan:
            scan.status = "failed"
            scan.log = (scan.log or "") + f"\n[ERROR] {str(e)}"
            scan.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def start_osint_scan(domain: str, company_name: str = "") -> str:
    """Start an OSINT scan in a background thread. Returns scan_id."""
    db = SessionLocal()
    try:
        scan = OsintScan(
            domain=domain,
            company_name=company_name or domain.split(".")[0].title(),
            status="running",
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        scan_id = scan.scan_id

        thread = threading.Thread(
            target=run_osint_scan_background,
            args=(scan_id, domain, company_name or domain.split(".")[0].title()),
            daemon=True,
        )
        thread.start()
        return scan_id
    finally:
        db.close()
