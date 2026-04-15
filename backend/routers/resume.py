"""
Resume Router — SkillLens v4
==============================
Routes:
  POST /api/resume/upload  — Upload PDF, extract text/skills/ATS score
  POST /api/resume/rewrite — Auto-rewrite resume for ATS optimisation (NEW)
  GET  /api/resume/{id}    — Fetch stored analysis
  GET  /api/resume/        — List recent analyses
"""

import json
import os
import re
from typing import List, Dict
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db, ResumeAnalysis
from services.resume_parser import (
    extract_text_from_pdf,
    extract_pdf_metadata,
    extract_contact_info,
    detect_resume_sections,
    calculate_resume_completeness,
    calculate_readability,
)
from services.nlp_service import (
    extract_skills,
    extract_contextual_experience,
    WEAK_VERB_MAP,
)

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class RewriteRequest(BaseModel):
    analysis_id:     int
    job_description: str
    missing_skills:  List[str] = []
    github_projects: List[Dict] = []  # {title, bullet} from GitHub Bullets tab


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    db:   Session    = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extracted_text = extract_text_from_pdf(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        meta = extract_pdf_metadata(file_bytes)
        ats_parsability = calculate_readability(
            text        = meta["text"] or extracted_text,
            page_count  = meta.get("page_count",  1),
            char_count  = meta.get("char_count",  len(extracted_text)),
            image_count = meta.get("image_count", 0),
        )
    except Exception:
        ats_parsability = calculate_readability(extracted_text)

    detected_skills       = extract_skills(extracted_text)
    contact_info          = extract_contact_info(extracted_text)
    sections              = detect_resume_sections(extracted_text)
    completeness          = calculate_resume_completeness(contact_info, sections, detected_skills)
    contextual_experience = extract_contextual_experience(extracted_text, detected_skills)

    analysis = ResumeAnalysis(
        filename        = file.filename,
        extracted_text  = extracted_text,
        detected_skills = json.dumps(detected_skills),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return {
        "analysis_id":           analysis.id,
        "filename":              file.filename,
        "detected_skills":       detected_skills,
        "skill_count":           len(detected_skills),
        "contact_info":          contact_info,
        "sections_detected":     {k: bool(v.strip()) for k, v in sections.items()},
        "resume_completeness":   completeness,
        "ats_parsability":       ats_parsability,
        "contextual_experience": contextual_experience,
        "preview_text":          extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
    }


# ── Auto-Rewrite ──────────────────────────────────────────────────────────────

@router.post("/rewrite")
async def rewrite_resume(
    request: RewriteRequest,
    db:      Session = Depends(get_db),
):
    """
    Auto-rewrite the resume to improve ATS match score.

    Strategy (no LLM key required):
      1. Load the stored resume text from the DB.
      2. Identify weak action verbs and replace them with strong alternatives.
      3. Weave missing skills into existing bullet points only where they
         logically fit — zero hallucination of new jobs or experience.
      4. Append a concise "Key Technical Skills" summary section listing
         newly integrated keywords so ATS parsers can find them at the top.
      5. Calculate a simulated new score and return a detailed changelog.

    When an LLM API key is available, replace _rewrite_with_rules() with
    an LLM call using the prompt template at the bottom of this file.
    """
    analysis = db.query(ResumeAnalysis).filter(
        ResumeAnalysis.id == request.analysis_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis ID {request.analysis_id} not found.")
    if not analysis.extracted_text:
        raise HTTPException(status_code=400, detail="No resume text found. Please upload the resume first.")

    old_score = float(analysis.match_score or 0.0)
    original_text = analysis.extracted_text

    # Try LLM-based rewrite first, fall back to rules
    try:
        rewritten, changelog = _rewrite_with_gemini(
            resume_text     = original_text,
            missing_skills  = request.missing_skills,
            job_description = request.job_description,
            github_projects = request.github_projects,
        )
    except Exception as gemini_err:
        print(f"[rewrite] Gemini failed ({gemini_err}), falling back to rule-based rewriter.")
        rewritten, changelog = _rewrite_with_rules(
            resume_text     = original_text,
            missing_skills  = request.missing_skills,
            job_description = request.job_description,
        )

    # Simulate new score: each missing skill woven in adds ~3-5 points
    skills_added    = sum(1 for entry in changelog if "woven" in entry.lower() or "added" in entry.lower() or "project" in entry.lower())
    verbs_fixed     = sum(1 for entry in changelog if "verb" in entry.lower())
    score_boost     = min(skills_added * 4.5 + verbs_fixed * 1.5, 30.0)
    new_score       = min(round(old_score + score_boost, 1), 98.0)
    score_increase  = f"+{round(new_score - old_score, 1)}%"

    return {
        "rewritten_text":    rewritten,
        "original_text":     original_text,
        "old_score":         old_score,
        "new_score":         new_score,
        "simulated_new_score": int(new_score),
        "score_increase":    score_increase,
        "changelog":         changelog,
    }


def _rewrite_with_gemini(
    resume_text:     str,
    missing_skills:  List[str],
    job_description: str,
    github_projects: List[Dict] = [],
) -> tuple:
    """
    Gemini LLM-based surgical resume rewriter.
    Preserves original structure; only replaces weak verbs and injects projects.

    Returns (rewritten_text: str, changelog: List[str])
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("GEMINI_API_KEY is not set.")

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Build the projects injection instruction
    projects_instruction = ""
    if github_projects:
        project_lines = []
        for p in github_projects:
            title  = p.get("title", "Untitled Project")
            bullet = p.get("bullet", "")
            if bullet:
                project_lines.append(f"  - {title}: {bullet}")
        if project_lines:
            projects_instruction = (
                "\n\nGITHUB PROJECTS TO INJECT:\n"
                "Find the existing 'Projects' section in the resume. If none exists, "
                "create a 'PROJECTS' section directly below the Experience/Work section. "
                "Append these project entries cleanly using the project name as a sub-heading "
                "and the bullet as a bullet point beneath it:\n"
                + "\n".join(project_lines)
            )

    prompt = (
        "You are an elite ATS Resume Optimisation Expert acting as a SURGICAL EDITOR.\n\n"
        "ABSOLUTE RULES — violating ANY of these is a failure:\n"
        "1. OUTPUT THE EXACT SAME LAYOUT — preserve every section header, every line break, "
        "every date range, every company name, every degree. Do NOT reorder sections.\n"
        "2. ONLY replace weak action verbs (worked, helped, assisted, involved, responsible, "
        "participated, contributed, supported, handled, did, used, performed, utilised, utilized) "
        "with strong past-tense action verbs (built, engineered, designed, implemented, led, "
        "architected, optimised, reduced, increased, improved, automated, delivered, deployed, "
        "streamlined, spearheaded).\n"
        "3. ZERO HALLUCINATION — never invent new jobs, degrees, companies, years, or experience. "
        "Never add skills the candidate doesn't have. Never change dates or titles.\n"
        "4. If missing_skills are provided, you may NATURALLY weave 1-2 of the most relevant ones "
        "into existing bullet points ONLY where they logically fit the candidate's actual described work. "
        "Do NOT force keywords where they don't belong.\n"
        "5. Do NOT add any header like 'KEY TECHNICAL SKILLS' or reformat the skills section.\n"
        "6. Keep the same whitespace pattern, the same indentation, the same bullet characters.\n"
        f"{projects_instruction}\n\n"
        f"MISSING SKILLS (weave naturally if possible): {', '.join(missing_skills[:8])}\n\n"
        f"JOB DESCRIPTION (for context only — do NOT copy from it):\n{job_description[:600]}\n\n"
        f"ORIGINAL RESUME TEXT (edit this surgically):\n{resume_text}\n\n"
        "OUTPUT FORMAT: Return ONLY valid JSON with exactly these keys:\n"
        '{\n'
        '  "rewritten_text": "the full edited resume text",\n'
        '  "changelog": ["change 1 description", "change 2 description", ...]\n'
        '}\n'
        "The changelog should list each specific verb replacement and any project injection made. "
        "Return ONLY the JSON — no markdown fences, no commentary."
    )

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

    result = json.loads(raw)
    rewritten = result.get("rewritten_text", resume_text)
    changelog = result.get("changelog", ["Resume reviewed — no changes needed."])

    if not changelog:
        changelog = ["Resume reviewed — no changes needed."]

    return rewritten, changelog




@router.get("/{analysis_id}")
async def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    analysis = db.query(ResumeAnalysis).filter(ResumeAnalysis.id == analysis_id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return {
        "analysis_id":     analysis.id,
        "filename":        analysis.filename,
        "detected_skills": json.loads(analysis.detected_skills) if analysis.detected_skills else [],
        "match_score":     analysis.match_score,
        "created_at":      analysis.created_at.isoformat() if analysis.created_at else None,
    }


@router.get("/")
async def list_analyses(db: Session = Depends(get_db)):
    analyses = db.query(ResumeAnalysis).order_by(ResumeAnalysis.created_at.desc()).limit(20).all()
    return [
        {
            "id":          a.id,
            "filename":    a.filename,
            "match_score": a.match_score,
            "created_at":  a.created_at.isoformat() if a.created_at else None,
        }
        for a in analyses
    ]