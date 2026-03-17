"""
ML-Based Job Recommendation Service
======================================
Uses scikit-learn TF-IDF + cosine similarity to match candidate skills
to predefined job roles and generate ranked recommendations.
"""

import json
import numpy as np
from typing import List, Dict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ─────────────────────────────────────────────────────────────────────────────
# Learning resources mapped to skill keywords
# ─────────────────────────────────────────────────────────────────────────────
LEARNING_RESOURCES = {
    "python": [
        {"platform": "Coursera", "course": "Python for Everybody", "url": "https://www.coursera.org/specializations/python"},
        {"platform": "YouTube", "course": "Python Full Course - freeCodeCamp", "url": "https://www.youtube.com/watch?v=rfscVS0vtbw"},
    ],
    "machine learning": [
        {"platform": "Coursera", "course": "Machine Learning Specialization (Andrew Ng)", "url": "https://www.coursera.org/specializations/machine-learning-introduction"},
        {"platform": "Udemy", "course": "Machine Learning A-Z", "url": "https://www.udemy.com/course/machinelearning/"},
    ],
    "deep learning": [
        {"platform": "Coursera", "course": "Deep Learning Specialization", "url": "https://www.coursera.org/specializations/deep-learning"},
        {"platform": "YouTube", "course": "Deep Learning - MIT 6.S191", "url": "https://www.youtube.com/watch?v=QDX-1M5Nj7s"},
    ],
    "tensorflow": [
        {"platform": "Coursera", "course": "TensorFlow Developer Professional Certificate", "url": "https://www.coursera.org/professional-certificates/tensorflow-in-practice"},
        {"platform": "YouTube", "course": "TensorFlow 2.0 Complete Course", "url": "https://www.youtube.com/watch?v=tPYj3fFJGjk"},
    ],
    "pytorch": [
        {"platform": "Udemy", "course": "PyTorch for Deep Learning", "url": "https://www.udemy.com/course/pytorch-for-deep-learning/"},
        {"platform": "YouTube", "course": "PyTorch Tutorials - Official", "url": "https://www.youtube.com/playlist?list=PLhhyoLH6IjfxeoooqP9rhU3HJIAVAJ3Vz"},
    ],
    "sql": [
        {"platform": "Coursera", "course": "SQL for Data Science", "url": "https://www.coursera.org/learn/sql-for-data-science"},
        {"platform": "YouTube", "course": "SQL Tutorial - Full Database Course", "url": "https://www.youtube.com/watch?v=HXV3zeQKqGY"},
    ],
    "docker": [
        {"platform": "Udemy", "course": "Docker and Kubernetes: The Complete Guide", "url": "https://www.udemy.com/course/docker-and-kubernetes-the-complete-guide/"},
        {"platform": "YouTube", "course": "Docker Crash Course", "url": "https://www.youtube.com/watch?v=pg19Z8LL06w"},
    ],
    "aws": [
        {"platform": "Coursera", "course": "AWS Fundamentals Specialization", "url": "https://www.coursera.org/specializations/aws-fundamentals"},
        {"platform": "Udemy", "course": "AWS Certified Solutions Architect", "url": "https://www.udemy.com/course/aws-certified-solutions-architect-associate-saa-c03/"},
    ],
    "react": [
        {"platform": "Udemy", "course": "React - The Complete Guide", "url": "https://www.udemy.com/course/react-the-complete-guide-incl-redux/"},
        {"platform": "YouTube", "course": "React Course - Beginner's Tutorial", "url": "https://www.youtube.com/watch?v=bMknfKXIFA8"},
    ],
    "javascript": [
        {"platform": "Coursera", "course": "JavaScript for Beginners", "url": "https://www.coursera.org/specializations/javascript-beginner"},
        {"platform": "YouTube", "course": "JavaScript Full Course - freeCodeCamp", "url": "https://www.youtube.com/watch?v=PkZNo7MFNFg"},
    ],
    "nlp": [
        {"platform": "Coursera", "course": "Natural Language Processing Specialization", "url": "https://www.coursera.org/specializations/natural-language-processing"},
        {"platform": "YouTube", "course": "NLP with Python - Sentdex", "url": "https://www.youtube.com/watch?v=FLZvOKSCkxY"},
    ],
    "data visualization": [
        {"platform": "Coursera", "course": "Data Visualization with Python", "url": "https://www.coursera.org/learn/python-for-data-visualization"},
        {"platform": "YouTube", "course": "Matplotlib Tutorial", "url": "https://www.youtube.com/watch?v=3Xc3CA655Y4"},
    ],
    "kubernetes": [
        {"platform": "Udemy", "course": "Certified Kubernetes Administrator (CKA)", "url": "https://www.udemy.com/course/certified-kubernetes-administrator-with-practice-tests/"},
        {"platform": "YouTube", "course": "Kubernetes Tutorial for Beginners", "url": "https://www.youtube.com/watch?v=X48VuDVv0do"},
    ],
    "pandas": [
        {"platform": "Udemy", "course": "Data Analysis with Pandas and Python", "url": "https://www.udemy.com/course/data-analysis-with-pandas/"},
        {"platform": "YouTube", "course": "Pandas Tutorial - Corey Schafer", "url": "https://www.youtube.com/watch?v=ZyhVh-qRZPA"},
    ],
    "statistics": [
        {"platform": "Coursera", "course": "Statistics with Python Specialization", "url": "https://www.coursera.org/specializations/statistics-with-python"},
        {"platform": "YouTube", "course": "Statistics - CrashCourse", "url": "https://www.youtube.com/watch?v=zouPoc49xbk"},
    ],
}

DEFAULT_RESOURCES = [
    {"platform": "Coursera", "course": "Search for courses on Coursera", "url": "https://www.coursera.org"},
    {"platform": "Udemy", "course": "Browse related Udemy courses", "url": "https://www.udemy.com"},
    {"platform": "YouTube", "course": "Search tutorials on YouTube", "url": "https://www.youtube.com"},
]


def get_learning_resources(missing_skills: List[str]) -> Dict[str, List[dict]]:
    """
    Return learning resources for each missing skill.
    
    Args:
        missing_skills: List of skill names the candidate is missing
        
    Returns:
        Dict mapping skill → list of resource dicts
    """
    resources = {}
    for skill in missing_skills[:10]:  # Cap at 10 skills to avoid overwhelming
        resources[skill] = LEARNING_RESOURCES.get(skill, DEFAULT_RESOURCES)
    return resources


def recommend_jobs(resume_skills: List[str], db_session) -> List[dict]:
    """
    Use TF-IDF + cosine similarity to rank job roles against the candidate's skills.
    
    Args:
        resume_skills: List of skills extracted from the resume
        db_session:    SQLAlchemy database session
        
    Returns:
        List of top job role dicts with similarity scores, sorted descending
    """
    from models.database import JobRole

    if not resume_skills:
        return []

    # Load all job roles from the database
    job_roles = db_session.query(JobRole).all()
    if not job_roles:
        return []

    # Prepare text corpus: candidate + all job roles
    candidate_text = " ".join(resume_skills)
    job_texts = []
    job_meta = []

    for role in job_roles:
        required = json.loads(role.required_skills)
        job_texts.append(" ".join(required))
        job_meta.append({
            "id": role.id,
            "title": role.title,
            "category": role.category,
            "required_skills": required
        })

    # TF-IDF vectorization across all documents
    corpus = [candidate_text] + job_texts
    vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b\w[\w\s/\.\+\#\-]+\b")
    tfidf_matrix = vectorizer.fit_transform(corpus)

    # Compute cosine similarity between candidate (row 0) and all jobs
    candidate_vector = tfidf_matrix[0]
    job_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(candidate_vector, job_vectors)[0]

    # Build ranked results
    recommendations = []
    for idx, score in enumerate(similarities):
        meta = job_meta[idx]
        resume_set = set(resume_skills)
        required_set = set(meta["required_skills"])
        overlap = resume_set & required_set
        missing = required_set - resume_set

        recommendations.append({
            "title": meta["title"],
            "category": meta["category"],
            "similarity_score": round(float(score) * 100, 1),
            "matching_skills": sorted(list(overlap)),
            "missing_skills": sorted(list(missing)),
            "required_skills": meta["required_skills"]
        })

    # Sort by similarity score descending; return top 5
    recommendations.sort(key=lambda x: x["similarity_score"], reverse=True)
    return recommendations[:5]


def generate_resume_suggestions(
    resume_skills: List[str],
    missing_skills: List[str],
    sections: dict,
    contact_info: dict
) -> List[str]:
    """
    Generate actionable, human-readable suggestions for improving the resume.
    
    Args:
        resume_skills:  Skills already on the resume
        missing_skills: Skills missing compared to job description
        sections:       Detected resume sections
        contact_info:   Detected contact information
        
    Returns:
        List of suggestion strings
    """
    suggestions = []

    # Missing critical skills
    if missing_skills:
        top_missing = missing_skills[:5]
        suggestions.append(
            f"🎯 Add these high-priority skills to your Skills section: {', '.join(top_missing)}"
        )

    # Missing contact info
    if not contact_info.get("linkedin"):
        suggestions.append("🔗 Add your LinkedIn profile URL — recruiters actively look for this")

    if not contact_info.get("email"):
        suggestions.append("📧 Ensure your professional email address is clearly visible")

    # Missing sections
    if not sections.get("summary", "").strip():
        suggestions.append("📝 Add a 3-4 sentence professional summary at the top of your resume")

    if not sections.get("projects", "").strip():
        suggestions.append("💼 Include a Projects section with 2-3 relevant technical projects")

    if not sections.get("certifications", "").strip():
        suggestions.append("🏆 List any certifications (Google, AWS, Coursera, etc.) to boost credibility")

    # Skill count advice
    if len(resume_skills) < 8:
        suggestions.append("🛠️ Expand your skills list — aim for at least 10 technical skills")

    # Generic quality tips
    suggestions.append("📊 Quantify your achievements (e.g., 'Improved performance by 30%')")
    suggestions.append("🔑 Use keywords from the job description to pass ATS filters")
    suggestions.append("📋 Keep resume to 1-2 pages; use bullet points for readability")

    return suggestions
