"""
Resume Router
==============
API endpoints for uploading and parsing resumes.
"""

import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session

from models.database import get_db, ResumeAnalysis
from services.resume_parser import (
    extract_text_from_pdf,
    extract_contact_info,
    detect_resume_sections,
    calculate_resume_completeness
)
from services.nlp_service import extract_skills

router = APIRouter()


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF resume, extract text and skills.
    
    Returns:
        Analysis ID, extracted text, detected skills, contact info, resume score
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Read file bytes
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Extract text from PDF
    try:
        extracted_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # NLP processing
    detected_skills = extract_skills(extracted_text)
    contact_info = extract_contact_info(extracted_text)
    sections = detect_resume_sections(extracted_text)
    completeness = calculate_resume_completeness(contact_info, sections, detected_skills)

    # Save to database
    analysis = ResumeAnalysis(
        filename=file.filename,
        extracted_text=extracted_text,
        detected_skills=json.dumps(detected_skills),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "analysis_id": analysis.id,
        "filename": file.filename,
        "detected_skills": detected_skills,
        "skill_count": len(detected_skills),
        "contact_info": contact_info,
        "sections_detected": {k: bool(v.strip()) for k, v in sections.items()},
        "resume_completeness": completeness,
        "preview_text": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text
    }


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    """Retrieve a previously stored resume analysis by ID."""
    analysis = db.query(ResumeAnalysis).filter(ResumeAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return {
        "analysis_id": analysis.id,
        "filename": analysis.filename,
        "detected_skills": json.loads(analysis.detected_skills) if analysis.detected_skills else [],
        "match_score": analysis.match_score,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None
    }


@router.get("/")
async def list_analyses(db: Session = Depends(get_db)):
    """List all previous resume analyses."""
    analyses = db.query(ResumeAnalysis).order_by(ResumeAnalysis.created_at.desc()).limit(20).all()
    return [
        {
            "id": a.id,
            "filename": a.filename,
            "match_score": a.match_score,
            "created_at": a.created_at.isoformat() if a.created_at else None
        }
        for a in analyses
    ]
