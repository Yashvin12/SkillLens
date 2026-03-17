"""
User Router — SkillLens v3
============================
All profile, settings, password-change, and history endpoints.
Every route requires a valid JWT (Bearer token).

Endpoints:
  GET    /user/profile           → Full profile + preferences + stats
  PUT    /user/update-profile    → Update name / email
  POST   /user/change-password   → Verify old pw, set new pw (bcrypt)
  GET    /user/preferences       → Get theme / language / notifications / layout
  PUT    /user/preferences       → Save preferences
  GET    /user/history           → Paginated analysis history
  DELETE /user/history           → Clear all history for the user
"""

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
import re

from models.database import get_db, User, UserPreferences, AnalysisHistory
from services.auth_service import (
    require_current_user, hash_password, verify_password
)

router = APIRouter(
    prefix="/user",
    tags=["User Settings"]
)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class UpdateProfileRequest(BaseModel):
    name: str
    email: str

    @field_validator("name")
    @classmethod
    def name_ok(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v.strip()

    @field_validator("email")
    @classmethod
    def email_ok(cls, v):
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
            raise ValueError("Invalid email address")
        return v.lower().strip()


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def pw_strong(cls, v):
        if len(v) < 6:
            raise ValueError("New password must be at least 6 characters")
        return v

    @field_validator("confirm_password")
    @classmethod
    def pw_match(cls, v, info):
        if "new_password" in info.data and v != info.data["new_password"]:
            raise ValueError("Passwords do not match")
        return v


class PreferencesRequest(BaseModel):
    theme:                      Optional[str] = "dark"    # "dark" | "light"
    language:                   Optional[str] = "en"      # "en"   | "hi"
    layout:                     Optional[str] = "detailed"
    notify_job_recommendations: Optional[bool] = True
    notify_learning_resources:  Optional[bool] = True


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_prefs(user: User, db: Session) -> UserPreferences:
    """Fetch or lazily create a UserPreferences row for the user."""
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


def _prefs_dict(prefs: UserPreferences) -> dict:
    return {
        "theme":                      prefs.theme,
        "language":                   prefs.language,
        "layout":                     prefs.layout,
        "notify_job_recommendations": prefs.notify_job_recommendations,
        "notify_learning_resources":  prefs.notify_learning_resources,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/profile")
async def get_profile(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """
    Full user profile: personal info, preferences, analysis stats,
    and the 5 most recent history entries.
    """
    prefs = _get_or_create_prefs(current_user, db)

    total = db.query(AnalysisHistory).filter(
        AnalysisHistory.user_id == current_user.id
    ).count()

    best = db.query(AnalysisHistory).filter(
        AnalysisHistory.user_id == current_user.id
    ).order_by(AnalysisHistory.ats_score.desc()).first()

    recent = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.user_id == current_user.id)
        .order_by(AnalysisHistory.created_at.desc())
        .limit(5)
        .all()
    )

    history_list = [
        {
            "id":                r.id,
            "resume_name":       r.resume_name,
            "ats_score":         r.ats_score,
            "missing_skills":    json.loads(r.missing_skills)    if r.missing_skills    else [],
            "matched_skills":    json.loads(r.matched_skills)    if r.matched_skills    else [],
            "recommended_roles": json.loads(r.recommended_roles) if r.recommended_roles else [],
            "created_at":        r.created_at.isoformat()        if r.created_at        else None,
        }
        for r in recent
    ]

    return {
        "id":             current_user.id,
        "name":           current_user.name,
        "email":          current_user.email,
        "member_since":   current_user.created_at.isoformat() if current_user.created_at else None,
        "total_analyses": total,
        "best_score":     round(best.ats_score, 1) if best else 0,
        "preferences":    _prefs_dict(prefs),
        "recent_history": history_list,
    }


@router.put("/update-profile")
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Update name and/or email. Rejects duplicate emails from other accounts."""
    # Check email collision (skip if same user)
    if request.email != current_user.email:
        clash = db.query(User).filter(
            User.email == request.email,
            User.id != current_user.id
        ).first()
        if clash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This email is already used by another account"
            )

    current_user.name  = request.name
    current_user.email = request.email
    db.commit()
    db.refresh(current_user)

    # Refresh the stored localStorage cache token hint
    return {
        "message":    "Profile updated successfully",
        "user_name":  current_user.name,
        "user_email": current_user.email,
        "user_id":    current_user.id,
    }


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Verify current password then update to a bcrypt-hashed new password."""
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    current_user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Return the user's current preferences."""
    prefs = _get_or_create_prefs(current_user, db)
    return _prefs_dict(prefs)


@router.put("/preferences")
async def update_preferences(
    request: PreferencesRequest,
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Persist theme, language, layout, and notification toggles."""
    prefs = _get_or_create_prefs(current_user, db)

    if request.theme    in ("dark", "light"):      prefs.theme    = request.theme
    if request.language in ("en", "hi"):           prefs.language = request.language
    if request.layout   in ("compact","detailed"): prefs.layout   = request.layout
    prefs.notify_job_recommendations = request.notify_job_recommendations
    prefs.notify_learning_resources  = request.notify_learning_resources
    prefs.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(prefs)
    return {"message": "Preferences saved", **_prefs_dict(prefs)}


@router.get("/history")
async def get_history(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Return the full paginated history for the authenticated user."""
    records = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.user_id == current_user.id)
        .order_by(AnalysisHistory.created_at.desc())
        .all()
    )
    return [
        {
            "id":                        r.id,
            "resume_name":               r.resume_name,
            "ats_score":                 r.ats_score,
            "missing_skills":            json.loads(r.missing_skills)    if r.missing_skills    else [],
            "matched_skills":            json.loads(r.matched_skills)    if r.matched_skills    else [],
            "recommended_roles":         json.loads(r.recommended_roles) if r.recommended_roles else [],
            "job_description_preview":   r.job_description_preview,
            "created_at":                r.created_at.isoformat()        if r.created_at        else None,
        }
        for r in records
    ]


@router.delete("/history")
async def delete_history(
    current_user: User = Depends(require_current_user),
    db: Session = Depends(get_db)
):
    """Delete ALL analysis history records for the authenticated user."""
    deleted = (
        db.query(AnalysisHistory)
        .filter(AnalysisHistory.user_id == current_user.id)
        .delete()
    )
    db.commit()
    return {"message": f"Deleted {deleted} history record(s)"}

