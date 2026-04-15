"""
Resume Parsing Service — SkillLens v4
=======================================
Upgrades from v3:
  - extract_text_from_pdf now collects page/block metadata for ATS scoring
  - calculate_readability(): ATS parsability score (0-100) + issue list
  - All existing public functions preserved with identical signatures
"""

import re
from typing import Optional, Dict, List, Tuple

try:
    import fitz  # PyMuPDF — optional; graceful fallback if not installed
    _FITZ_AVAILABLE = True
except ImportError:
    _FITZ_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# PDF text extraction — now also returns metadata for ATS scoring
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF file.
    Raises ValueError if the file cannot be read or yields no text.
    """
    if not _FITZ_AVAILABLE:
        raise ValueError("PyMuPDF (fitz) is not installed. Run: pip install pymupdf")
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        pages = []
        for page in doc:
            t = page.get_text("text")
            if t.strip():
                pages.append(t)
        doc.close()
        text = "\n".join(pages)
        if not text.strip():
            raise ValueError(
                "No text extracted — PDF may be image-based or encrypted."
            )
        return text
    except fitz.FileDataError:
        raise ValueError("Invalid or corrupted PDF file.")


def extract_pdf_metadata(file_bytes: bytes) -> dict:
    """
    Extract structural metadata needed for ATS readability scoring.
    Returns: { page_count, char_count, image_count, block_count, text }
    Falls back to zeros if fitz is unavailable.
    """
    if not _FITZ_AVAILABLE:
        return {"page_count": 1, "char_count": 0, "image_count": 0,
                "block_count": 0, "text": ""}
    try:
        doc         = fitz.open(stream=file_bytes, filetype="pdf")
        page_count  = len(doc)
        char_count  = 0
        image_count = 0
        block_count = 0
        pages_text  = []

        for page in doc:
            t = page.get_text("text")
            char_count  += len(t)
            pages_text.append(t)
            # Count images on this page
            image_count += len(page.get_images(full=False))
            # Count text blocks (high count + short avg → multi-column)
            blocks       = page.get_text("blocks")
            block_count += len(blocks)

        doc.close()
        return {
            "page_count":  page_count,
            "char_count":  char_count,
            "image_count": image_count,
            "block_count": block_count,
            "text":        "\n".join(pages_text),
        }
    except Exception:
        return {"page_count": 1, "char_count": 0, "image_count": 0,
                "block_count": 0, "text": ""}


# ─────────────────────────────────────────────────────────────────────────────
# ATS Readability / Parsability Score
# ─────────────────────────────────────────────────────────────────────────────

def calculate_readability(
    text:        str,
    page_count:  int = 1,
    char_count:  int = None,
    image_count: int = 0,
    block_count: int = None,
) -> dict:
    """
    Analyse how well an ATS system will parse this resume.

    Checks:
      - Text density per page (low = image-heavy)
      - Short-line ratio (high = multi-column layout)
      - Pipe character count (table artefacts)
      - Image saturation
      - Non-ASCII character density
      - Missing standard section headers

    Returns:
      ats_parsability_score (0-100), grade (A-D), label, issues list
    """
    if char_count is None:
        char_count = len(text)

    score  = 100
    issues: List[str] = []

    # 1. Text density per page
    cpp = char_count / max(page_count, 1)
    if cpp < 300:
        score -= 30
        issues.append(
            "Very low text density — PDF appears to be image-based or heavily graphical. "
            "ATS systems cannot read images."
        )
    elif cpp < 700:
        score -= 12
        issues.append(
            "Low text density per page — some content may not be parsed. "
            "Replace graphic elements with plain text."
        )

    # 2. Multi-column detection via short-line ratio
    lines = [l for l in text.split('\n') if l.strip()]
    if lines:
        short = sum(1 for l in lines if 0 < len(l.strip()) < 35)
        ratio = short / len(lines)
        if ratio > 0.65:
            score -= 20
            issues.append(
                f"High short-line ratio ({ratio:.0%}) strongly suggests a multi-column layout. "
                "ATS parsers read left-to-right and will mix up columns. Use single-column format."
            )
        elif ratio > 0.45:
            score -= 8
            issues.append(
                f"Moderate short-line ratio ({ratio:.0%}) — possible two-column layout. "
                "Consider a single-column template for better ATS compatibility."
            )

    # 3. Table artefacts (pipe characters)
    pipes = text.count('|')
    if pipes > 10:
        score -= 15
        issues.append(
            f"{pipes} pipe '|' characters detected — indicates a table. "
            "ATS parsers frequently misread tables. Replace with plain bullet points."
        )

    # 4. Image saturation
    if image_count > 5:
        score -= 10
        issues.append(
            f"{image_count} images found. Excessive images reduce parsability. "
            "Remove decorative images and replace photo sections with text."
        )

    # 5. Non-ASCII characters
    non_ascii = len(re.findall(r'[^\x00-\x7F]', text))
    if non_ascii > 50:
        score -= 8
        issues.append(
            f"{non_ascii} non-ASCII characters detected. Fancy bullets (▸, ✦) or "
            "special quotes can cause encoding errors in ATS. Use standard ASCII."
        )

    # 6. Missing standard section headers
    headers_found = set(re.findall(
        r'\b(experience|education|skills|projects|summary|certifications|objective)\b',
        text.lower()
    ))
    if len(headers_found) < 2:
        score -= 10
        issues.append(
            f"Only {len(headers_found)} standard section header(s) found. "
            "ATS systems use headers to categorise content. Add: Experience, Education, Skills."
        )

    # 7. Page count warning
    if page_count > 2:
        score -= 5
        issues.append(
            f"Resume is {page_count} pages. Most ATS systems only index the first 2 pages. "
            "Condense to 1–2 pages."
        )

    score = max(0, min(100, score))

    if score >= 85:
        grade, label = "A", "Excellent ATS compatibility"
    elif score >= 70:
        grade, label = "B", "Good ATS compatibility — minor issues"
    elif score >= 50:
        grade, label = "C", "Fair — some ATS systems may misparse content"
    else:
        grade, label = "D", "Poor — significant formatting issues detected"

    return {
        "ats_parsability_score": score,
        "grade":  grade,
        "label":  label,
        "issues": issues,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Contact extraction (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def extract_contact_info(text: str) -> dict:
    emails    = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    phones    = re.findall(r'(\+?\d[\d\s\-().]{7,}\d)', text)
    linkedins = re.findall(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)

    name = ""
    for line in text.split('\n'):
        line = line.strip()
        if line and len(line.split()) in (2, 3) and re.match(r'^[A-Za-z\s]+$', line):
            name = line
            break

    return {
        "name":     name,
        "email":    emails[0]          if emails    else "",
        "phone":    phones[0].strip()  if phones    else "",
        "linkedin": linkedins[0]       if linkedins else "",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Section detection (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def detect_resume_sections(text: str) -> dict:
    sections = {
        "education": "", "experience": "", "skills": "",
        "projects": "", "certifications": "", "summary": ""
    }
    section_patterns = {
        "education":      r'(education|academic|qualifications)',
        "experience":     r'(experience|employment|work history|career)',
        "skills":         r'(skills|technical skills|core competencies|technologies)',
        "projects":       r'(projects|portfolio|work samples)',
        "certifications": r'(certifications?|certificates?|licenses?|credentials)',
        "summary":        r'(summary|objective|profile|about me)',
    }
    lines           = text.split('\n')
    current_section = None
    content         = {k: [] for k in sections}

    for line in lines:
        ll = line.strip().lower()
        matched = None
        for sec, pat in section_patterns.items():
            if re.search(pat, ll) and len(line.strip()) < 50:
                matched = sec
                break
        if matched:
            current_section = matched
        elif current_section:
            content[current_section].append(line)

    for sec in sections:
        sections[sec] = '\n'.join(content[sec]).strip()
    return sections


# ─────────────────────────────────────────────────────────────────────────────
# Resume completeness score (unchanged)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_resume_completeness(contact_info: dict, sections: dict, skills: list) -> dict:
    checklist = []
    score     = 0

    for field, label, pts in [
        ("email",    "Email address present",    5),
        ("phone",    "Phone number present",      5),
        ("name",     "Candidate name detected",   5),
        ("linkedin", "LinkedIn profile present",  5),
    ]:
        if contact_info.get(field):
            checklist.append({"item": label, "status": True,  "points": pts})
            score += pts
        else:
            checklist.append({"item": label, "status": False, "points": 0})

    for sec, pts in {"experience": 15, "education": 10, "skills": 10, "projects": 5}.items():
        if sections.get(sec, "").strip():
            checklist.append({"item": f"{sec.title()} section present", "status": True,  "points": pts})
            score += pts
        else:
            checklist.append({"item": f"{sec.title()} section present", "status": False, "points": 0})

    if len(skills) >= 10:
        checklist.append({"item": "10+ technical skills detected", "status": True,  "points": 25}); score += 25
    elif len(skills) >= 5:
        checklist.append({"item": "5+ technical skills detected",  "status": True,  "points": 15}); score += 15
    else:
        checklist.append({"item": "Sufficient skills detected",    "status": False, "points": 0})

    if sections.get("certifications", "").strip():
        checklist.append({"item": "Certifications present", "status": True,  "points": 15}); score += 15
    else:
        checklist.append({"item": "Certifications present", "status": False, "points": 0})

    score = min(score, 100)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    return {"score": score, "grade": grade, "checklist": checklist}