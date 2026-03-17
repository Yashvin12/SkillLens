"""
NLP Skill Extraction Service
==============================
Uses spaCy + keyword matching to extract technical skills
from resume text and job descriptions.
"""

import re
import json
from typing import List, Set

# ─────────────────────────────────────────────────────────────────────────────
# Master skill dictionary: category → list of skill keywords
# ─────────────────────────────────────────────────────────────────────────────
SKILL_DICTIONARY = {
    "programming_languages": [
        "python", "java", "javascript", "typescript", "c++", "c#", "c", "r",
        "go", "rust", "kotlin", "swift", "scala", "ruby", "php", "perl",
        "bash", "shell", "matlab", "dart", "elixir"
    ],
    "web_technologies": [
        "html", "css", "react", "angular", "vue", "node.js", "express",
        "django", "flask", "fastapi", "spring", "asp.net", "next.js",
        "graphql", "rest api", "jquery", "bootstrap", "tailwind", "webpack",
        "sass", "less", "svelte"
    ],
    "databases": [
        "sql", "mysql", "postgresql", "mongodb", "sqlite", "oracle",
        "redis", "cassandra", "elasticsearch", "dynamodb", "firebase",
        "mariadb", "neo4j", "influxdb", "database design"
    ],
    "cloud_devops": [
        "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "jenkins",
        "terraform", "ansible", "helm", "linux", "git", "github", "gitlab",
        "bitbucket", "nginx", "apache", "microservices", "serverless"
    ],
    "data_ml": [
        "machine learning", "deep learning", "nlp", "natural language processing",
        "computer vision", "tensorflow", "pytorch", "scikit-learn", "keras",
        "pandas", "numpy", "matplotlib", "seaborn", "spark", "hadoop",
        "data analysis", "data visualization", "statistics", "tableau",
        "power bi", "data mining", "feature engineering", "model deployment"
    ],
    "mobile": [
        "android", "ios", "flutter", "react native", "swift", "kotlin",
        "xamarin", "ionic", "mobile development"
    ],
    "security": [
        "cybersecurity", "network security", "penetration testing",
        "vulnerability assessment", "siem", "firewalls", "encryption",
        "oauth", "jwt", "ssl", "tls"
    ],
    "soft_skills": [
        "leadership", "communication", "teamwork", "problem solving",
        "project management", "agile", "scrum", "time management"
    ],
    "tools": [
        "excel", "jira", "confluence", "slack", "figma", "photoshop",
        "postman", "selenium", "jest", "pytest", "jupyter", "vscode",
        "intellij", "xcode", "android studio"
    ]
}

# Flatten all skills into a single set for quick lookup
ALL_SKILLS: Set[str] = set()
for skills in SKILL_DICTIONARY.values():
    ALL_SKILLS.update(skills)


def preprocess_text(text: str) -> str:
    """Lowercase and normalize whitespace in text."""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_skills(text: str) -> List[str]:
    """
    Extract technical skills from raw text using keyword matching.
    
    Strategy:
    1. Normalize the text
    2. For each known skill, check if it appears as a whole word/phrase
    3. Return deduplicated, sorted list of matched skills
    
    Args:
        text: Raw resume or job description text
        
    Returns:
        Sorted list of detected skill strings
    """
    if not text:
        return []

    normalized = preprocess_text(text)
    found_skills = set()

    for skill in ALL_SKILLS:
        # Use word-boundary regex to avoid partial matches
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, normalized):
            found_skills.add(skill)

    return sorted(list(found_skills))


def get_skill_categories(skills: List[str]) -> dict:
    """
    Group a list of skills by their category.
    
    Args:
        skills: List of skill strings
        
    Returns:
        Dict mapping category name → list of skills in that category
    """
    categorized = {}
    for category, category_skills in SKILL_DICTIONARY.items():
        matched = [s for s in skills if s in category_skills]
        if matched:
            categorized[category] = matched
    return categorized


def calculate_skill_gap(resume_skills: List[str], job_skills: List[str]) -> dict:
    """
    Compare resume skills with job requirements and compute gap metrics.
    
    Args:
        resume_skills: Skills extracted from the resume
        job_skills:    Skills extracted from the job description
        
    Returns:
        Dict with keys: matched_skills, missing_skills, match_score, extra_skills
    """
    resume_set = set(resume_skills)
    job_set = set(job_skills)

    matched_skills = list(resume_set & job_set)
    missing_skills = list(job_set - resume_set)
    extra_skills = list(resume_set - job_set)   # skills candidate has beyond JD

    if len(job_set) > 0:
        match_score = round((len(matched_skills) / len(job_set)) * 100, 2)
    else:
        match_score = 0.0

    return {
        "matched_skills": sorted(matched_skills),
        "missing_skills": sorted(missing_skills),
        "extra_skills": sorted(extra_skills),
        "match_score": match_score
    }
