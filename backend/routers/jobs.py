"""
Jobs Router
============
API endpoints for job description analysis and job role listings.
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db, JobRole
from services.nlp_service import extract_skills

router = APIRouter()


class JobDescriptionRequest(BaseModel):
    job_description: str
    analysis_id: int | None = None  # Optionally link to a resume analysis


@router.post("/analyze")
async def analyze_job_description(
    request: JobDescriptionRequest,
    db: Session = Depends(get_db)
):
    """
    Parse a pasted job description and extract required skills.
    
    Returns:
        List of extracted job skills, skill count
    """
    if not request.job_description.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")

    extracted_skills = extract_skills(request.job_description)

    # Update analysis record if an ID was provided
    if request.analysis_id:
        from models.database import ResumeAnalysis
        analysis = db.query(ResumeAnalysis).filter(
            ResumeAnalysis.id == request.analysis_id
        ).first()
        if analysis:
            analysis.job_description = request.job_description
            analysis.job_skills = json.dumps(extracted_skills)
            db.commit()

    return {
        "extracted_skills": extracted_skills,
        "skill_count": len(extracted_skills),
        "job_description_preview": request.job_description[:300] + "..." if len(request.job_description) > 300 else request.job_description
    }


@router.get("/roles")
async def list_job_roles(db: Session = Depends(get_db)):
    """Return all available job roles in the system."""
    roles = db.query(JobRole).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "category": r.category,
            "required_skills": json.loads(r.required_skills)
        }
        for r in roles
    ]


@router.get("/roles/{role_id}")
async def get_job_role(role_id: int, db: Session = Depends(get_db)):
    """Return details for a specific job role."""
    role = db.query(JobRole).filter(JobRole.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Job role not found.")
    return {
        "id": role.id,
        "title": role.title,
        "category": role.category,
        "required_skills": json.loads(role.required_skills)
    }
