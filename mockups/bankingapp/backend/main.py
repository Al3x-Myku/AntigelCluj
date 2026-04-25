"""Banking App — FastAPI entrypoint."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

from backend.database import init_db

app = FastAPI(title="SecurBank", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# Router
from backend.routers.auth import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])


@app.on_event("startup")
def on_startup():
    """Init DB and seed demo data."""
    try:
        init_db()
        print("[OK] SQLite database ready, tables created")
    except Exception as e:
        print(f"[WARN] DB init failed: {e}")
        return

    from backend.database import SessionLocal
    from backend.models.user import User
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            from backend.seed import run_seed
            run_seed()
    except Exception as e:
        print(f"[WARN] Seed failed: {e}")
    finally:
        db.close()


# Pages
@app.get("/", response_class=HTMLResponse)
async def login_page():
    return FileResponse(str(FRONTEND_DIR / "login.html"))


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", "9000")),
        reload=True,
    )
