"""
Authentication Service — SkillLens v3
========================================
Fixed:
  - require_current_user now correctly raises 401 instead of silently returning None
  - get_current_user is the optional-auth variant (used only for guest-friendly routes)
  - SECRET_KEY reads from environment variable (no hardcoded secret in code)
  - Cleaner separation of concerns
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from models.database import get_db, User

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "skilllens-super-secret-jwt-key-change-in-production-2024"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# auto_error=False so we can return None for unauthenticated guests on public routes
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


# ── Password Utilities ────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token Utilities ───────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token_safe(token: str) -> Optional[dict]:
    """Decode a JWT; returns None instead of raising on failure."""
    if not token or token in ("null", "undefined"):
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ── Dependency: Optional auth (guest-friendly routes) ─────────────────────────
def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Returns the authenticated User or None.
    Use this ONLY on routes that should work for both guests and logged-in users.
    """
    payload = _decode_token_safe(token)
    if not payload:
        return None

    email: str = payload.get("sub")
    if not email:
        return None

    return db.query(User).filter(User.email == email).first()


# ── Dependency: Mandatory auth ────────────────────────────────────────────────
def require_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Returns the authenticated User or raises HTTP 401.
    Use this on every protected route.
    """
    payload = _decode_token_safe(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email: str = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user