"""Auth router — login and JWT token management."""

import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Form
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt, JWTError

from backend.database import get_db
from backend.models.user import User

router = APIRouter()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRY = int(os.getenv("JWT_EXPIRY_MINUTES", "60"))


def create_token(user_id: int, email: str, role: str) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRY),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify a JWT token. Returns the payload or raises."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.post("/login")
def login(
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    """Authenticate user and return JWT."""
    user = db.query(User).filter(User.email == email).first()
    if not user or not pwd_ctx.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_token(user.id, user.email, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
        },
    }


@router.get("/me")
def get_me(token: str, db: Session = Depends(get_db)):
    """Return current user from JWT token."""
    payload = verify_token(token)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
    }
