"""PhishGuard — FastAPI Application Entrypoint."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from backend.database import init_db

# ─── Create App ──────────────────────────────────────────────
app = FastAPI(
    title="PhishGuard",
    description="Phishing Simulation & Defense Platform",
    version="1.0.0",
)

# ─── CORS ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Static Files ────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)

# Mount frontend directories
for subdir in ["attack", "defense", "shared"]:
    dir_path = FRONTEND_DIR / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    app.mount(f"/static/{subdir}", StaticFiles(directory=str(dir_path)), name=f"static_{subdir}")

# ─── Include Routers ─────────────────────────────────────────
from backend.routers.attack import router as attack_router
from backend.routers.defense import router as defense_router
from backend.routers.phish import router as phish_router

app.include_router(attack_router, prefix="/api/attack", tags=["Attack (Red Team)"])
app.include_router(defense_router, prefix="/api/defense", tags=["Defense (Blue Team)"])
app.include_router(phish_router, tags=["Phishing Pages"])


# ─── Startup ─────────────────────────────────────────────────
@app.on_event("startup")
def on_startup():
    """Initialize database and seed data."""
    init_db()
    # Auto seed if DB is empty
    from backend.database import SessionLocal
    from backend.models.account import Account
    db = SessionLocal()
    try:
        if db.query(Account).count() == 0:
            print("📦 Empty database detected — running seed...")
            from backend.seed import run_seed
            run_seed()
    finally:
        db.close()


# ─── Frontend Page Routes ────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to attack dashboard."""
    return """<html><head><meta http-equiv="refresh" content="0;url=/attack/"></head></html>"""


@app.get("/attack/", response_class=HTMLResponse)
@app.get("/attack", response_class=HTMLResponse)
async def attack_index():
    return FileResponse(str(FRONTEND_DIR / "attack" / "index.html"))


@app.get("/attack/campaign/create", response_class=HTMLResponse)
async def attack_campaign_create():
    return FileResponse(str(FRONTEND_DIR / "attack" / "campaign_create.html"))


@app.get("/attack/campaign/{campaign_id}", response_class=HTMLResponse)
async def attack_campaign_detail(campaign_id: int):
    return FileResponse(str(FRONTEND_DIR / "attack" / "campaign_detail.html"))


@app.get("/defense/", response_class=HTMLResponse)
@app.get("/defense", response_class=HTMLResponse)
async def defense_index():
    return FileResponse(str(FRONTEND_DIR / "defense" / "index.html"))


@app.get("/defense/monitor", response_class=HTMLResponse)
async def defense_monitor():
    return FileResponse(str(FRONTEND_DIR / "defense" / "login_monitor.html"))


@app.get("/defense/lockdown", response_class=HTMLResponse)
async def defense_lockdown():
    return FileResponse(str(FRONTEND_DIR / "defense" / "lockdown.html"))


# ─── Health ──────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "PhishGuard"}


# ─── Run ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "8000")),
        reload=True,
    )
