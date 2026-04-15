"""
Authentication Router — SkillLens v3
Fixed: duplicate imports, removed unused EmailStr/OAuth2PasswordRequestForm
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
import re
import json

from models.database import get_db, User, AnalysisHistory
from services.auth_service import (
    hash_password, verify_password,
    create_access_token, require_current_user,
)

router = APIRouter()

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    confirm_password: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_valid(cls, v):
        if not re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', v):
            raise ValueError("Invalid email address")
        return v.lower().strip()

    @field_validator("password")
    @classmethod
    def password_strong(cls, v):
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="An account with this email already exists")
    user = User(name=request.name, email=request.email,
                password_hash=hash_password(request.password))
    db.add(user); db.commit(); db.refresh(user)
    token = create_access_token({"sub": user.email, "user_id": user.id})
    return {"message": f"Welcome to SkillLens, {user.name}!", "access_token": token,
            "token_type": "bearer", "user_name": user.name,
            "user_email": user.email, "user_id": user.id}

@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.lower().strip()).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect email or password")
    token = create_access_token({"sub": user.email, "user_id": user.id})
    return {"message": f"Welcome back, {user.name}!", "access_token": token,
            "token_type": "bearer", "user_name": user.name,
            "user_email": user.email, "user_id": user.id}

@router.get("/profile")
async def get_profile(current_user: User = Depends(require_current_user),
                      db: Session = Depends(get_db)):
    total = db.query(AnalysisHistory).filter(AnalysisHistory.user_id == current_user.id).count()
    history = (db.query(AnalysisHistory).filter(AnalysisHistory.user_id == current_user.id)
               .order_by(AnalysisHistory.created_at.desc()).limit(5).all())
    return {
        "id": current_user.id, "name": current_user.name, "email": current_user.email,
        "member_since": current_user.created_at.isoformat() if current_user.created_at else None,
        "total_analyses": total,
        "recent_history": [{"id": h.id, "resume_name": h.resume_name, "ats_score": h.ats_score,
            "missing_skills": json.loads(h.missing_skills) if h.missing_skills else [],
            "recommended_roles": json.loads(h.recommended_roles) if h.recommended_roles else [],
            "created_at": h.created_at.isoformat() if h.created_at else None} for h in history]
    }