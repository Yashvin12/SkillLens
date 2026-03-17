"""
Analysis Router
================
Core API endpoint: performs full skill gap analysis, ATS scoring,
job recommendations, suggestions, and learning resources.
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional

from models.database import get_db, ResumeAnalysis
from services.nlp_service import extract_skills, calculate_skill_gap, get_skill_categories
from services.ml_service import recommend_jobs, get_learning_resources, generate_resume_suggestions
from services.resume_parser import detect_resume_sections, extract_contact_info

router = APIRouter()


class FullAnalysisRequest(BaseModel):
    analysis_id: int
    job_description: str


class QuickAnalysisRequest(BaseModel):
    """For demo/testing without uploading a PDF."""
    resume_text: str
    job_description: str


@router.post("/full")
async def full_analysis(request: FullAnalysisRequest, db: Session = Depends(get_db)):
    """
    Run the complete analysis pipeline:
    1. Load resume from DB
    2. Extract job skills from JD
    3. Compute skill gap
    4. Score ATS match
    5. Recommend jobs
    6. Generate improvement suggestions
    7. Suggest learning resources
    
    Returns comprehensive analysis results.
    """
    # Fetch existing resume analysis
    analysis = db.query(ResumeAnalysis).filter(
        ResumeAnalysis.id == request.analysis_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis ID {request.analysis_id} not found.")

    if not analysis.detected_skills:
        raise HTTPException(status_code=400, detail="Resume skills not yet extracted. Please upload the resume first.")

    resume_skills = json.loads(analysis.detected_skills)
    resume_text = analysis.extracted_text or ""

    # Extract job skills from the submitted JD
    job_skills = extract_skills(request.job_description)
    if not job_skills:
        raise HTTPException(status_code=400, detail="No recognizable skills found in the job description. Please provide a more detailed job description.")

    # Skill gap analysis
    gap_result = calculate_skill_gap(resume_skills, job_skills)

    # Resume sections & contact info (for suggestions)
    sections = detect_resume_sections(resume_text)
    contact_info = extract_contact_info(resume_text)

    # ML-based job recommendations
    job_recommendations = recommend_jobs(resume_skills, db)

    # Resume improvement suggestions
    suggestions = generate_resume_suggestions(
        resume_skills,
        gap_result["missing_skills"],
        sections,
        contact_info
    )

    # Learning resources for missing skills
    learning_resources = get_learning_resources(gap_result["missing_skills"])

    # Skill categorization for chart display
    resume_skill_categories = get_skill_categories(resume_skills)
    job_skill_categories = get_skill_categories(job_skills)

    # Persist results to database
    analysis.job_description = request.job_description
    analysis.job_skills = json.dumps(job_skills)
    analysis.missing_skills = json.dumps(gap_result["missing_skills"])
    analysis.match_score = gap_result["match_score"]
    analysis.job_recommendations = json.dumps(job_recommendations)
    analysis.suggestions = json.dumps(suggestions)
    db.commit()

    return {
        "analysis_id": analysis.id,
        "filename": analysis.filename,

        # Skills breakdown
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "matched_skills": gap_result["matched_skills"],
        "missing_skills": gap_result["missing_skills"],
        "extra_skills": gap_result["extra_skills"],

        # ATS Score
        "match_score": gap_result["match_score"],
        "ats_label": _ats_label(gap_result["match_score"]),

        # Chart data
        "skill_match_chart": {
            "matched": len(gap_result["matched_skills"]),
            "missing": len(gap_result["missing_skills"]),
            "extra": len(gap_result["extra_skills"]),
            "total_job_skills": len(job_skills),
            "total_resume_skills": len(resume_skills)
        },
        "resume_skill_categories": resume_skill_categories,
        "job_skill_categories": job_skill_categories,

        # Recommendations & suggestions
        "job_recommendations": job_recommendations,
        "suggestions": suggestions,
        "learning_resources": learning_resources,
    }


@router.post("/quick")
async def quick_analysis(request: QuickAnalysisRequest, db: Session = Depends(get_db)):
    """
    Run a full analysis from raw text without needing to upload a PDF.
    Useful for testing and demo purposes.
    """
    if not request.resume_text.strip() or not request.job_description.strip():
        raise HTTPException(status_code=400, detail="Both resume_text and job_description are required.")

    resume_skills = extract_skills(request.resume_text)
    job_skills = extract_skills(request.job_description)

    gap_result = calculate_skill_gap(resume_skills, job_skills)
    sections = detect_resume_sections(request.resume_text)
    contact_info = extract_contact_info(request.resume_text)

    # Save to DB for history
    analysis = ResumeAnalysis(
        filename="quick_analysis.txt",
        extracted_text=request.resume_text,
        detected_skills=json.dumps(resume_skills),
        job_description=request.job_description,
        job_skills=json.dumps(job_skills),
        missing_skills=json.dumps(gap_result["missing_skills"]),
        match_score=gap_result["match_score"],
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    job_recommendations = recommend_jobs(resume_skills, db)
    suggestions = generate_resume_suggestions(resume_skills, gap_result["missing_skills"], sections, contact_info)
    learning_resources = get_learning_resources(gap_result["missing_skills"])

    analysis.job_recommendations = json.dumps(job_recommendations)
    analysis.suggestions = json.dumps(suggestions)
    db.commit()

    return {
        "analysis_id": analysis.id,
        "resume_skills": resume_skills,
        "job_skills": job_skills,
        "matched_skills": gap_result["matched_skills"],
        "missing_skills": gap_result["missing_skills"],
        "extra_skills": gap_result["extra_skills"],
        "match_score": gap_result["match_score"],
        "ats_label": _ats_label(gap_result["match_score"]),
        "skill_match_chart": {
            "matched": len(gap_result["matched_skills"]),
            "missing": len(gap_result["missing_skills"]),
            "extra": len(gap_result["extra_skills"]),
            "total_job_skills": len(job_skills),
            "total_resume_skills": len(resume_skills)
        },
        "resume_skill_categories": get_skill_categories(resume_skills),
        "job_skill_categories": get_skill_categories(job_skills),
        "job_recommendations": job_recommendations,
        "suggestions": suggestions,
        "learning_resources": learning_resources,
    }


@router.get("/history")
async def get_analysis_history(db: Session = Depends(get_db)):
    """Return the 10 most recent analyses."""
    records = db.query(ResumeAnalysis).order_by(
        ResumeAnalysis.created_at.desc()
    ).limit(10).all()

    return [
        {
            "id": r.id,
            "filename": r.filename,
            "match_score": r.match_score,
            "detected_skills_count": len(json.loads(r.detected_skills)) if r.detected_skills else 0,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


def _ats_label(score: float) -> str:
    """Return a human-readable ATS match label based on score."""
    if score >= 80:
        return "Excellent Match 🟢"
    elif score >= 60:
        return "Good Match 🟡"
    elif score >= 40:
        return "Fair Match 🟠"
    else:
        return "Poor Match 🔴"
