"""
Resume Parsing Service
========================
Handles PDF upload, text extraction, and basic resume section detection.
Uses PyMuPDF (fitz) for PDF parsing.
"""

import fitz  # PyMuPDF
import io
import re
from typing import Optional


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF file provided as bytes.
    
    Args:
        file_bytes: Raw bytes of the PDF file
        
    Returns:
        Extracted text as a single string
        
    Raises:
        ValueError: If the PDF cannot be read or is empty
    """
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        full_text = []

        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text("text")
            if page_text.strip():
                full_text.append(page_text)

        pdf_document.close()
        extracted = "\n".join(full_text)

        if not extracted.strip():
            raise ValueError("No text could be extracted from the PDF. It may be image-based or encrypted.")

        return extracted

    except fitz.FileDataError:
        raise ValueError("Invalid or corrupted PDF file.")


def extract_contact_info(text: str) -> dict:
    """
    Extract basic contact information from resume text using regex.
    
    Args:
        text: Raw resume text
        
    Returns:
        Dict with name, email, phone, linkedin fields (may be empty strings)
    """
    # Email regex
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)

    # Phone regex (handles common formats)
    phone_pattern = r'(\+?\d[\d\s\-().]{7,}\d)'
    phones = re.findall(phone_pattern, text)

    # LinkedIn URL
    linkedin_pattern = r'linkedin\.com/in/[\w\-]+'
    linkedins = re.findall(linkedin_pattern, text, re.IGNORECASE)

    # Best-guess name: first non-empty line that looks like a name
    name = ""
    for line in text.split('\n'):
        line = line.strip()
        if line and len(line.split()) in (2, 3) and re.match(r'^[A-Za-z\s]+$', line):
            name = line
            break

    return {
        "name": name,
        "email": emails[0] if emails else "",
        "phone": phones[0].strip() if phones else "",
        "linkedin": linkedins[0] if linkedins else ""
    }


def detect_resume_sections(text: str) -> dict:
    """
    Identify major sections in the resume (education, experience, skills, etc.)
    
    Args:
        text: Raw resume text
        
    Returns:
        Dict mapping section_name → section_text
    """
    sections = {
        "education": "",
        "experience": "",
        "skills": "",
        "projects": "",
        "certifications": "",
        "summary": ""
    }

    # Patterns for section headers
    section_patterns = {
        "education": r'(education|academic|qualifications)',
        "experience": r'(experience|employment|work history|career)',
        "skills": r'(skills|technical skills|core competencies|technologies)',
        "projects": r'(projects|portfolio|work samples)',
        "certifications": r'(certifications?|certificates?|licenses?|credentials)',
        "summary": r'(summary|objective|profile|about me)'
    }

    lines = text.split('\n')
    current_section = None
    section_content = {k: [] for k in sections}

    for line in lines:
        line_lower = line.strip().lower()
        matched_section = None

        for section, pattern in section_patterns.items():
            if re.search(pattern, line_lower) and len(line.strip()) < 50:
                matched_section = section
                break

        if matched_section:
            current_section = matched_section
        elif current_section:
            section_content[current_section].append(line)

    for section in sections:
        sections[section] = '\n'.join(section_content[section]).strip()

    return sections


def calculate_resume_completeness(contact_info: dict, sections: dict, skills: list) -> dict:
    """
    Calculate how complete and ATS-friendly a resume is.
    
    Returns:
        Dict with score (0-100), checklist, and overall grade
    """
    checklist = []
    score = 0

    # Contact information checks (20 points)
    if contact_info.get("email"):
        checklist.append({"item": "Email address present", "status": True, "points": 5})
        score += 5
    else:
        checklist.append({"item": "Email address present", "status": False, "points": 0})

    if contact_info.get("phone"):
        checklist.append({"item": "Phone number present", "status": True, "points": 5})
        score += 5
    else:
        checklist.append({"item": "Phone number present", "status": False, "points": 0})

    if contact_info.get("name"):
        checklist.append({"item": "Candidate name detected", "status": True, "points": 5})
        score += 5
    else:
        checklist.append({"item": "Candidate name detected", "status": False, "points": 0})

    if contact_info.get("linkedin"):
        checklist.append({"item": "LinkedIn profile present", "status": True, "points": 5})
        score += 5
    else:
        checklist.append({"item": "LinkedIn profile present", "status": False, "points": 0})

    # Section checks (40 points)
    section_points = {"experience": 15, "education": 10, "skills": 10, "projects": 5}
    for section, pts in section_points.items():
        if sections.get(section, "").strip():
            checklist.append({"item": f"{section.title()} section present", "status": True, "points": pts})
            score += pts
        else:
            checklist.append({"item": f"{section.title()} section present", "status": False, "points": 0})

    # Skills check (25 points)
    if len(skills) >= 10:
        checklist.append({"item": "10+ technical skills detected", "status": True, "points": 25})
        score += 25
    elif len(skills) >= 5:
        checklist.append({"item": "5+ technical skills detected", "status": True, "points": 15})
        score += 15
    else:
        checklist.append({"item": "Sufficient skills detected", "status": False, "points": 0})

    # Certifications bonus (15 points)
    if sections.get("certifications", "").strip():
        checklist.append({"item": "Certifications/credentials present", "status": True, "points": 15})
        score += 15
    else:
        checklist.append({"item": "Certifications/credentials present", "status": False, "points": 0})

    # Grade assignment
    if score >= 85:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 55:
        grade = "C"
    else:
        grade = "D"

    return {"score": min(score, 100), "grade": grade, "checklist": checklist}
