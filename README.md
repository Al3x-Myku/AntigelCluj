# 🛡 PhishGuard

**Phishing Simulation & Defense Platform** — A dual-dashboard security tool that lets Red Teams launch simulated phishing campaigns across 6 channels and Blue Teams detect anomalous logins, ban attackers, and lock down compromised accounts in real time.

Built for the Cluj Hackathon 2026.

---

## 📸 Screenshots

| Defense Overview | Login Monitor | Lockdown Manager |
|:---:|:---:|:---:|
| MCD anomaly histogram, live stats, ban list | Color-coded event feed with anomaly scores | Per-account resource tree with freeze controls |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker** (optional — for Mailhog email capture and Redis)
- Two mini PCs on the same LAN (optional — as "victim" machines)

### 1. Clone & Setup

```bash
git clone https://github.com/Al3x-Myku/AntigelCluj.git
cd AntigelCluj

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` to match your network:

```env
# Update with your actual IPs
VICTIM_PC1_IP=192.168.1.101
VICTIM_PC2_IP=192.168.1.102

# If running Mailhog via Docker
SMTP_HOST=localhost
SMTP_PORT=1025

# Anomaly engine: "sklearn" (CPU) or "onnx" (GPU-trained model)
ANOMALY_ENGINE=sklearn
```

### 3. Run the Server

```bash
source venv/bin/activate
python -m backend.main
```

The server starts at **http://localhost:8000**. On first launch, the database is auto-seeded with:
- 10 demo accounts (2 mapped to victim mini-PC IPs)
- 530 login events (500 normal + 30 anomalous) for ML training

### 4. (Optional) Start Docker Services

```bash
docker-compose up -d
```

This starts:
- **Redis** (port 6379) — async campaign jobs + rate limiting
- **Mailhog** (SMTP on 1025, Web UI on 8025) — captures phishing emails

> The app works **without Docker** using in-memory fallbacks for Redis and mock senders for email.

---

## 🎮 How to Use — Demo Flow

### Step 1: Train the Anomaly Detector

1. Open **http://localhost:8000/defense/**
2. Click **🧠 Train Model** — trains MinCovDet on 500 normal login events
3. Click **📊 Score Events** — scores all events, flags ~30 as anomalous
4. The **Mahalanobis Distance Distribution** histogram appears with the chi²(0.975, df=8) = 17.53 threshold line

### Step 2: Simulate Attacks

1. On the Defense Overview, click **🔴 Simulate Attack Login** several times
2. Watch anomaly scores spike (scores in the hundreds/thousands vs. normal <17)
3. Go to **http://localhost:8000/defense/monitor** to see the live event feed — attack events are highlighted in red

### Step 3: Lock Down a Compromised Account

1. Go to **http://localhost:8000/defense/lockdown**
2. Find an account (e.g., `victim1`) and click **🔒 Lockdown**
3. Watch all resources flip: cards → frozen, sessions → revoked, subscriptions → suspended, API tokens → revoked
4. The audit trail logs every action with timestamp

### Step 4: Create a Phishing Campaign

1. Open **http://localhost:8000/attack/campaign/create**
2. Fill in the campaign name, toggle channels (Email, SMS, Telegram, etc.)
3. Upload a CSV file with targets (columns: `first_name, last_name, email, phone`)
4. Customize the message template using variables: `{{name}}`, `{{link}}`, `{{bank}}`
5. Click **🚀 Create Campaign**

### Step 5: Launch & Monitor

1. On the campaign detail page, click **🚀 Launch Campaign**
2. Watch live metrics update every 3 seconds:
   - **Funnel chart**: Targets → Sent → Clicked → Submitted
   - **Per-channel breakdown**: bar chart by channel
   - **Timeline**: messages sent over time
   - **Heatmap**: clicks by hour of day
3. Each target gets a unique tracking link (`/phish/{uuid}`)
4. When a target opens the link, they see a realistic fake bank login page
5. Credential submissions are captured and logged

### Step 6: Mini PC Demo (LAN)

1. Set `VICTIM_PC1_IP` and `VICTIM_PC2_IP` in `.env` to your mini PCs' IPs
2. On the mini PCs, open Mailhog at `http://<server-ip>:8025` to see phishing emails
3. Click the phishing link from the email — the PhishGuard server tracks the click
4. Submit credentials on the fake login page — they appear in the campaign detail view
5. On the defense console, the mini PCs' login events appear with their real IPs

---

## 🏗 Architecture

```
AntigelCluj/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint (auto-seeds DB)
│   ├── database.py              # SQLAlchemy engine/session (SQLite + WAL)
│   ├── seed.py                  # Demo data generator (Faker)
│   ├── routers/
│   │   ├── attack.py            # Campaign CRUD, launch, live stats
│   │   ├── defense.py           # Login events, anomaly scoring, lockdown, bans
│   │   └── phish.py             # Fake login pages, click/credential tracking
│   ├── services/
│   │   ├── campaign_runner.py   # RQ job (async) + sync fallback
│   │   ├── anomaly_detector.py  # MinCovDet Mahalanobis distance engine
│   │   ├── lockdown.py          # Full account resource freeze
│   │   ├── rate_limiter.py      # Fail2Ban-style sliding window (Redis/in-memory)
│   │   └── channels/
│   │       ├── email_sender.py  # smtplib → Mailhog
│   │       ├── sms_sender.py    # Mock adapter
│   │       ├── telegram_sender.py
│   │       ├── discord_sender.py
│   │       └── instagram_sender.py
│   └── ml/
│       ├── train_anomaly.py     # PyTorch LSTM autoencoder (GPU offline)
│       └── infer_anomaly.py     # ONNX runtime inference
├── frontend/
│   ├── attack/
│   │   ├── index.html           # Campaign list dashboard
│   │   ├── campaign_create.html # Campaign creation form
│   │   └── campaign_detail.html # Live metrics (Chart.js, 3s polling)
│   ├── defense/
│   │   ├── index.html           # Defense overview + MCD histogram
│   │   ├── login_monitor.html   # Live login event feed
│   │   └── lockdown.html        # Account resource lockdown manager
│   └── shared/
│       ├── nav.html             # Shared navbar (loaded via fetch)
│       └── charts.js            # Chart.js helper functions
├── docker-compose.yml           # Redis, Mailhog
├── Dockerfile
├── requirements.txt
└── .env                         # Configuration
```

---

## 🔬 Technical Details

### Anomaly Detection

- **Algorithm**: Minimum Covariance Determinant (MCD) via `sklearn.covariance.MinCovDet`
- **Feature vector** (8 dimensions per login event):
  ```
  [hour_of_day, day_of_week, login_failures_last_hour,
   ip_is_new, device_is_new, geo_distance_km,
   time_since_last_login_hrs, typing_speed_ms]
  ```
- **Threshold**: `chi2.ppf(0.975, df=8)` ≈ 17.53 (Mahalanobis distance)
- **GPU path** (optional): Train an LSTM autoencoder with PyTorch, export to ONNX, toggle with `ANOMALY_ENGINE=onnx`

### Rate Limiting (Fail2Ban-style)

- Sliding window tracking per IP and per username
- **Soft ban** (5 failures in 60s): CAPTCHA challenge
- **Hard ban** (10 failures in 60s): IP blocked for 1 hour
- Storage: Redis sorted sets (primary) or in-memory dict (fallback)

### Phishing Pages

- Fake bank login page with glassmorphism dark UI
- Each target gets a unique UUID token in their link for tracking
- Click tracking → credential capture → redirect to real site

---

## ⚠️ Known Limitations & Flaws

### Security & Scope

| Issue | Details |
|-------|---------|
| **No authentication** | The PhishGuard admin dashboards have no login — anyone with the URL can access them. In production, this would need auth + RBAC. |
| **Credentials stored in plaintext** | Captured phishing credentials are stored as plain text in SQLite. A real product would hash or not store them at all. |
| **No HTTPS** | The server runs on plain HTTP. Phishing links in a real scenario would need HTTPS to be convincing. |
| **SQLite single-writer** | SQLite is used for simplicity. Under heavy concurrent load (many campaigns + login events), it would bottleneck. PostgreSQL swap is straightforward. |

### Anomaly Detection

| Issue | Details |
|-------|---------|
| **MCD assumes Gaussian features** | MinCovDet works best when the underlying data distribution is roughly elliptical. Real login data may have multimodal patterns the MCD won't capture well. |
| **Static threshold** | The chi²(0.975) threshold is fixed. In production, you'd want adaptive thresholds per user based on their own behavioral baseline. |
| **No retraining pipeline** | The model is trained on-demand via a button click. There's no scheduled retraining as new normal data accumulates. |
| **Feature engineering is basic** | 8 features is a starting point. Real systems use hundreds (browser fingerprint entropy, session behavior sequences, mouse dynamics, etc.). |
| **ONNX path untested on GPU** | The LSTM autoencoder trainer and ONNX export are implemented but haven't been validated end-to-end on an actual GPU. |

### Campaign System

| Issue | Details |
|-------|---------|
| **Mock channels only** | SMS, WhatsApp, Telegram, Discord, and Instagram senders are mocks — they log messages but don't actually deliver. Only email (via Mailhog) works for real. |
| **No email open tracking** | Unlike GoPhish, there's no tracking pixel for email opens — we only track link clicks and form submissions. |
| **No A/B testing** | Campaign templates can't be split-tested across different message variants. |
| **Sync fallback blocks** | Without Redis, campaign execution runs synchronously in the request thread, which blocks the API for large campaigns. |
| **CSV parsing is fragile** | The CSV parser does minimal validation — malformed CSVs may cause silent failures. |

### Rate Limiting

| Issue | Details |
|-------|---------|
| **In-memory bans are per-process** | Without Redis, bans live in a Python dict and are lost on server restart. Multi-worker deployments won't share ban state. |
| **No CAPTCHA implementation** | Soft bans flag for CAPTCHA but there's no actual CAPTCHA challenge served — it's a placeholder. |
| **IP spoofing** | The rate limiter trusts `request.client.host`, which can be spoofed behind proxies without proper `X-Forwarded-For` handling. |

### Frontend

| Issue | Details |
|-------|---------|
| **No WebSocket** | All live feeds use `setInterval` polling (3–5s). WebSocket would reduce latency and server load. |
| **Charts destroy/recreate** | On each poll cycle, charts are destroyed and recreated rather than updated in-place, causing a brief flicker. |
| **No mobile optimization** | The dashboard is usable on mobile but not optimized — some charts may overflow on small screens. |
| **No error boundaries** | If the API is down, the frontend shows stale data rather than a clear error state. |

### Infrastructure

| Issue | Details |
|-------|---------|
| **No logging to file** | Logs go to stdout only. Production would need structured logging to files/ELK. |
| **No health checks in Docker** | The Docker Compose doesn't define health checks for service dependencies. |
| **No rate limiting on the API itself** | The Fail2Ban logic applies to simulated logins, but the API endpoints themselves have no rate limiting. |
| **No backup/recovery** | SQLite DB file can be lost. No backup strategy implemented. |

---

## 🔗 API Reference

### Attack (Red Team)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/attack/campaigns` | Create campaign (multipart form + CSV) |
| `GET` | `/api/attack/campaigns` | List all campaigns |
| `GET` | `/api/attack/campaigns/{id}` | Campaign detail with targets |
| `POST` | `/api/attack/campaigns/{id}/launch` | Launch campaign |
| `GET` | `/api/attack/stats/{id}` | Live metrics (poll every 3s) |

### Defense (Blue Team)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/defense/events` | Recent login events |
| `GET` | `/api/defense/anomalies` | Flagged anomalous events |
| `GET` | `/api/defense/dashboard` | Overview stats + score distribution |
| `POST` | `/api/defense/train` | Train MCD model |
| `POST` | `/api/defense/score` | Score all unscored events |
| `POST` | `/api/defense/simulate-login` | Inject test login event |
| `POST` | `/api/defense/lockdown/{id}` | Execute full account lockdown |
| `GET` | `/api/defense/lockdown/{id}/status` | Resource tree with statuses |
| `POST` | `/api/defense/lockdown/{id}/restore` | Restore locked account |
| `GET` | `/api/defense/bans` | Active IP ban list |
| `GET` | `/api/defense/accounts` | All accounts with resources |

### Phishing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/phish/{token}` | Serve fake login page + log click |
| `POST` | `/api/phish/{token}/submit` | Capture credentials |

---

## 🧪 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, SQLite |
| Frontend | HTML5, Bootstrap 5 (dark), Chart.js |
| ML | scikit-learn (MinCovDet), PyTorch (LSTM), ONNX Runtime |
| Queue | Redis + RQ (with in-memory fallback) |
| Email | smtplib + Mailhog (Docker) |
| Containers | Docker Compose (Redis, Mailhog) |

---

## 📚 References

- [GoPhish](https://github.com/gophish/gophish) — Campaign structure and metrics inspiration
- [Mailhog](https://github.com/mailhog/MailHog) — Local SMTP capture
- [scikit-learn MCD](https://scikit-learn.org/stable/modules/covariance.html#robust-covariance) — Mahalanobis distance
- [fail2ban](https://github.com/fail2ban/fail2ban) — Rate limiting logic inspiration
- [Redis Queue](https://python-rq.org/) — Async job processing

---

## 📄 License

MIT — This is a hackathon educational project. **All phishing simulation is strictly local. No real external targets are used.**