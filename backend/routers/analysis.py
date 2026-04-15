"""
Analysis Router — SkillLens v4
================================
Upgrades:
  - full_analysis and quick_analysis now return:
      semantic_matches      — alias/soft matches that boosted the score
      contextual_experience — skill → proof sentence from resume
      ats_parsability       — ATS format score (from upload, echoed here)
  - New route POST /api/analysis/analyze-verbs
  - New route POST /api/analysis/generate-cover-letter
  - All new fields use safe .get() fallbacks throughout
"""

import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional, Dict

from models.database import get_db, ResumeAnalysis, AnalysisHistory
from services.nlp_service import (
    extract_skills, calculate_skill_gap, get_skill_categories,
    extract_contextual_experience, analyse_verbs,
)
from services.ml_service import recommend_jobs, get_learning_resources, generate_resume_suggestions, generate_github_bullets
from services.resume_parser import detect_resume_sections, extract_contact_info
from services.github_service import scan_github_for_skills
from services.export_service import generate_ats_docx
from services.auth_service import get_current_user
from models.database import User

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class FullAnalysisRequest(BaseModel):
    analysis_id:     int
    job_description: str

class QuickAnalysisRequest(BaseModel):
    resume_text:     str
    job_description: str

class AnalyzeVerbsRequest(BaseModel):
    bullets: List[str]

class CoverLetterRequest(BaseModel):
    resume_name:      str       = "Candidate"
    matched_skills:   List[str] = []
    missing_skills:   List[str] = []
    job_description:  str       = ""
    target_role:      str       = "the position"
    candidate_name:   str       = ""

class GitHubBulletsRequest(BaseModel):
    github_username: str
    missing_skills:  List[str]

class ExportDocxRequest(BaseModel):
    rewritten_text: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_gap(gap: dict) -> dict:
    return {
        "matched_skills":   gap.get("matched_skills",   []),
        "missing_skills":   gap.get("missing_skills",   []),
        "extra_skills":     gap.get("extra_skills",     []),
        "match_score":      gap.get("match_score",      0.0),
        "semantic_matches": gap.get("semantic_matches", []),
    }

def _ats_label(score: float) -> str:
    if score >= 80: return "Excellent Match 🟢"
    if score >= 60: return "Good Match 🟡"
    if score >= 40: return "Fair Match 🟠"
    return "Poor Match 🔴"

def _extract_role_titles(json_str) -> list:
    if not json_str:
        return []
    try:
        recs = json.loads(json_str)
        return [r.get("title", "") for r in recs if isinstance(r, dict)][:3]
    except (json.JSONDecodeError, TypeError):
        return []


# ── Full analysis ─────────────────────────────────────────────────────────────

@router.post("/full")
async def full_analysis(
    request:      FullAnalysisRequest,
    db:           Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user),
):
    analysis = db.query(ResumeAnalysis).filter(
        ResumeAnalysis.id == request.analysis_id
    ).first()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis ID {request.analysis_id} not found.")
    if not analysis.detected_skills:
        raise HTTPException(status_code=400, detail="Resume skills not extracted yet. Upload the resume first.")

    resume_skills = json.loads(analysis.detected_skills)
    resume_text   = analysis.extracted_text or ""

    job_skills = extract_skills(request.job_description)
    if not job_skills:
        raise HTTPException(status_code=400, detail="No recognisable skills found in the job description.")

    gap_result   = _safe_gap(calculate_skill_gap(resume_skills, job_skills))
    sections     = detect_resume_sections(resume_text)
    contact_info = extract_contact_info(resume_text)

    job_recommendations = recommend_jobs(resume_skills, db)
    suggestions = generate_resume_suggestions(
        resume_skills,
        gap_result["missing_skills"],
        sections,
        contact_info,
        job_skills          = job_skills,
        job_recommendations = job_recommendations,
        resume_text         = resume_text,
        match_score         = gap_result["match_score"],
    )
    learning_resources    = get_learning_resources(gap_result["missing_skills"])
    contextual_experience = extract_contextual_experience(resume_text, resume_skills)

    # Persist
    analysis.job_description    = request.job_description
    analysis.job_skills         = json.dumps(job_skills)
    analysis.missing_skills     = json.dumps(gap_result["missing_skills"])
    analysis.match_score        = gap_result["match_score"]
    analysis.job_recommendations= json.dumps(job_recommendations)
    analysis.suggestions        = json.dumps(suggestions)
    db.commit()

    if current_user:
        db.add(AnalysisHistory(
            user_id                 = current_user.id,
            resume_name             = analysis.filename,
            ats_score               = gap_result["match_score"],
            missing_skills          = json.dumps(gap_result["missing_skills"]),
            matched_skills          = json.dumps(gap_result["matched_skills"]),
            recommended_roles       = json.dumps([r["title"] for r in job_recommendations[:3]]),
            job_description_preview = request.job_description[:300],
            resume_analysis_id      = analysis.id,
        ))
        db.commit()

    return {
        "analysis_id":  analysis.id,
        "filename":     analysis.filename,
        # Skills
        "resume_skills":           resume_skills,
        "job_skills":              job_skills,
        "matched_skills":          gap_result["matched_skills"],
        "missing_skills":          gap_result["missing_skills"],
        "extra_skills":            gap_result["extra_skills"],
        # Score
        "match_score":             gap_result["match_score"],
        "ats_label":               _ats_label(gap_result["match_score"]),
        # NEW: semantic match evidence
        "semantic_matches":        gap_result.get("semantic_matches", []),
        # Chart data
        "skill_match_chart": {
            "matched":           len(gap_result["matched_skills"]),
            "missing":           len(gap_result["missing_skills"]),
            "extra":             len(gap_result["extra_skills"]),
            "total_job_skills":  len(job_skills),
            "total_resume_skills": len(resume_skills),
        },
        "resume_skill_categories": get_skill_categories(resume_skills),
        "job_skill_categories":    get_skill_categories(job_skills),
        # NEW: contextual proof
        "contextual_experience":   contextual_experience,
        # Recommendations
        "job_recommendations":     job_recommendations,
        "suggestions":             suggestions,
        "learning_resources":      learning_resources,
    }


# ── Quick analysis ────────────────────────────────────────────────────────────

@router.post("/quick")
async def quick_analysis(request: QuickAnalysisRequest, db: Session = Depends(get_db)):
    if not request.resume_text.strip() or not request.job_description.strip():
        raise HTTPException(status_code=400, detail="Both resume_text and job_description are required.")

    resume_skills = extract_skills(request.resume_text)
    job_skills    = extract_skills(request.job_description)
    gap_result    = _safe_gap(calculate_skill_gap(resume_skills, job_skills))
    sections      = detect_resume_sections(request.resume_text)
    contact_info  = extract_contact_info(request.resume_text)

    analysis = ResumeAnalysis(
        filename       = "quick_analysis.txt",
        extracted_text = request.resume_text,
        detected_skills= json.dumps(resume_skills),
        job_description= request.job_description,
        job_skills     = json.dumps(job_skills),
        missing_skills = json.dumps(gap_result["missing_skills"]),
        match_score    = gap_result["match_score"],
    )
    db.add(analysis); db.commit(); db.refresh(analysis)

    job_recommendations = recommend_jobs(resume_skills, db)
    suggestions = generate_resume_suggestions(
        resume_skills, gap_result["missing_skills"], sections, contact_info,
        job_skills=job_skills, job_recommendations=job_recommendations,
        resume_text=request.resume_text, match_score=gap_result["match_score"],
    )
    learning_resources    = get_learning_resources(gap_result["missing_skills"])
    contextual_experience = extract_contextual_experience(request.resume_text, resume_skills)

    analysis.job_recommendations = json.dumps(job_recommendations)
    analysis.suggestions         = json.dumps(suggestions)
    db.commit()

    return {
        "analysis_id":             analysis.id,
        "resume_skills":           resume_skills,
        "job_skills":              job_skills,
        "matched_skills":          gap_result["matched_skills"],
        "missing_skills":          gap_result["missing_skills"],
        "extra_skills":            gap_result["extra_skills"],
        "match_score":             gap_result["match_score"],
        "ats_label":               _ats_label(gap_result["match_score"]),
        "semantic_matches":        gap_result.get("semantic_matches", []),
        "skill_match_chart": {
            "matched":             len(gap_result["matched_skills"]),
            "missing":             len(gap_result["missing_skills"]),
            "extra":               len(gap_result["extra_skills"]),
            "total_job_skills":    len(job_skills),
            "total_resume_skills": len(resume_skills),
        },
        "resume_skill_categories": get_skill_categories(resume_skills),
        "job_skill_categories":    get_skill_categories(job_skills),
        "contextual_experience":   contextual_experience,
        "job_recommendations":     job_recommendations,
        "suggestions":             suggestions,
        "learning_resources":      learning_resources,
    }


# ── /analyze-verbs ────────────────────────────────────────────────────────────

@router.post("/analyze-verbs")
async def analyze_verbs(request: AnalyzeVerbsRequest):
    """
    Accept a list of resume bullet points and return weak-verb analysis.
    Response: { results: [{ original, has_weak, weak_verbs: [{weak_verb, alternatives}] }] }
    """
    if not request.bullets:
        raise HTTPException(status_code=400, detail="bullets list cannot be empty.")
    if len(request.bullets) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 bullets per request.")

    results = analyse_verbs(request.bullets)
    weak_count = sum(1 for r in results if r["has_weak"])
    return {
        "results":    results,
        "total":      len(results),
        "weak_count": weak_count,
    }


# ── /generate-cover-letter ────────────────────────────────────────────────────

@router.post("/generate-cover-letter")
async def generate_cover_letter(request: CoverLetterRequest):
    """
    Generate a professional 3-paragraph cover letter.

    Uses a template engine for now (no LLM API key required).
    Swap the _build_cover_letter() call with an LLM call when a key is available.
    """
    letter = _build_cover_letter(
        candidate_name = request.candidate_name or "Hiring Manager",
        target_role    = request.target_role or "this position",
        matched_skills = request.matched_skills or [],
        missing_skills = request.missing_skills or [],
        jd_preview     = request.job_description[:400] if request.job_description else "",
    )
    return {
        "cover_letter": letter,
        "word_count":   len(letter.split()),
        "generated_by": "template",  # change to "llm" when API key is wired
    }


def _build_cover_letter(
    candidate_name: str,
    target_role:    str,
    matched_skills: List[str],
    missing_skills: List[str],
    jd_preview:     str,
) -> str:
    """
    Three-paragraph cover letter template.
    Wire in an LLM by replacing this function body with an API call.
    """
    top_matched = matched_skills[:5]
    top_missing = missing_skills[:3]

    matched_str = ", ".join(top_matched) if top_matched else "the relevant technical requirements"
    upskilling  = (
        f"I am also actively building my expertise in "
        f"{', '.join(top_missing)}, "
        f"and I expect to reach production-level proficiency within the next 60–90 days."
        if top_missing else
        "I am continuously expanding my knowledge to stay current with industry trends."
    )

    p1 = (
        f"I am writing to express my strong interest in the {target_role} role. "
        f"With proven hands-on experience in {matched_str}, "
        f"I am confident in my ability to contribute meaningfully from day one "
        f"and grow with your team."
    )

    p2 = (
        f"Throughout my career I have applied {top_matched[0] if top_matched else 'my technical skills'} "
        f"in production environments — delivering reliable, scalable solutions under real-world constraints. "
        f"I thrive in collaborative settings where technical rigour and clear communication are valued. "
        f"{upskilling}"
    )

    p3 = (
        f"I am excited about the opportunity to bring my background in "
        f"{matched_str} to your organisation and to take on the challenges described in this role. "
        f"I would welcome the chance to discuss how my skills align with your team's goals. "
        f"Thank you for your time and consideration."
    )

    return f"{p1}\n\n{p2}\n\n{p3}"


# ── /generate-github-bullets ──────────────────────────────────────────────────

@router.post("/generate-github-bullets")
async def generate_github_bullets_route(request: GitHubBulletsRequest):
    """
    Scan a GitHub profile for repos matching missing skills, then use
    Gemini to auto-generate STAR-method resume bullet points.

    Request : { github_username: str, missing_skills: [str] }
    Response: { github_username, skills_found, skills_not_found,
                repo_matches, generated_bullets }
    """
    if not request.github_username.strip():
        raise HTTPException(status_code=400, detail="GitHub username is required.")
    if not request.missing_skills:
        raise HTTPException(status_code=400, detail="missing_skills list cannot be empty.")
    if len(request.missing_skills) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 skills per request.")

    # Step 1 — Scan GitHub repos
    try:
        repo_matches = scan_github_for_skills(
            username=request.github_username.strip(),
            missing_skills=request.missing_skills,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {str(e)[:120]}")

    skills_found     = list(repo_matches.keys())
    skills_not_found = [s for s in request.missing_skills if s not in skills_found]

    # Step 2 — Generate bullets (only if we found matching repos)
    generated_bullets = {}
    if repo_matches:
        try:
            generated_bullets = generate_github_bullets(repo_matches)
        except EnvironmentError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Bullet generation failed: {str(e)[:120]}")

    return {
        "github_username":  request.github_username,
        "skills_found":     skills_found,
        "skills_not_found": skills_not_found,
        "repo_matches":     repo_matches,
        "generated_bullets": generated_bullets,
    }


# ── /export-docx ──────────────────────────────────────────────────────────────

# ── /export-docx ──────────────────────────────────────────────────────────────

@router.post("/export-docx")
async def export_docx(request: ExportDocxRequest):
    """
    Generate an ATS-optimised .docx resume from Auto Rewrite output.
    """
    if not request.rewritten_text or not request.rewritten_text.strip():
        raise HTTPException(
            status_code=400,
            detail="rewritten_text is empty. Run Auto Rewrite first.",
        )

    try:
        from services.export_service import generate_ats_docx

        docx_stream = generate_ats_docx(
            rewritten_text=request.rewritten_text,
        )

        return StreamingResponse(
            docx_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": 'attachment; filename="Polished_ATS_Resume.docx"',
            },
        )
    except Exception as e:
        print(f"DOCX Generation Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate DOCX: {str(e)}",
        )


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/history")
async def get_analysis_history(db: Session = Depends(get_db)):
    records = db.query(ResumeAnalysis).order_by(
        ResumeAnalysis.created_at.desc()
    ).limit(10).all()
    return [
        {
            "id":                    r.id,
            "filename":              r.filename,
            "match_score":           r.match_score,
            "missing_skills":        json.loads(r.missing_skills)   if r.missing_skills   else [],
            "recommended_roles":     _extract_role_titles(r.job_recommendations),
            "detected_skills_count": len(json.loads(r.detected_skills)) if r.detected_skills else 0,
            "created_at":            r.created_at.isoformat()       if r.created_at       else None,
        }
        for r in records
    ]