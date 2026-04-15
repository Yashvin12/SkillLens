"""
Database Models and Initialization — SkillLens v3
====================================================
Added: UserPreferences model for theme, language, notifications, layout.
All existing models unchanged.
"""

import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./resume_analyzer.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    """Registered users with hashed passwords."""
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    name          = Column(String(150), nullable=False)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    analyses    = relationship("AnalysisHistory", back_populates="user", cascade="all, delete")
    preferences = relationship("UserPreferences", back_populates="user",
                               uselist=False, cascade="all, delete")


class UserPreferences(Base):
    """Per-user settings: theme, language, notifications, layout."""
    __tablename__ = "user_preferences"

    id                          = Column(Integer, primary_key=True, index=True)
    user_id                     = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    theme                       = Column(String(10),  default="dark")       # "dark" | "light"
    language                    = Column(String(10),  default="en")         # "en" | "hi"
    layout                      = Column(String(20),  default="detailed")   # "compact" | "detailed"
    notify_job_recommendations  = Column(Boolean, default=True)
    notify_learning_resources   = Column(Boolean, default=True)
    created_at                  = Column(DateTime, default=datetime.utcnow)
    updated_at                  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="preferences")


class AnalysisHistory(Base):
    """Per-user analysis history records."""
    __tablename__ = "analysis_history"

    id                       = Column(Integer, primary_key=True, index=True)
    user_id                  = Column(Integer, ForeignKey("users.id"), nullable=True)
    resume_name              = Column(String(255), nullable=False)
    ats_score                = Column(Float, default=0.0)
    missing_skills           = Column(Text, nullable=True)
    matched_skills           = Column(Text, nullable=True)
    recommended_roles        = Column(Text, nullable=True)
    job_description_preview  = Column(Text, nullable=True)
    resume_analysis_id       = Column(Integer, nullable=True)
    created_at               = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="analyses")


class ResumeAnalysis(Base):
    """Stores each resume analysis session."""
    __tablename__ = "resume_analyses"

    id               = Column(Integer, primary_key=True, index=True)
    filename         = Column(String(255), nullable=False)
    extracted_text   = Column(Text, nullable=True)
    detected_skills  = Column(Text, nullable=True)
    job_description  = Column(Text, nullable=True)
    job_skills       = Column(Text, nullable=True)
    missing_skills   = Column(Text, nullable=True)
    match_score      = Column(Float, default=0.0)
    job_recommendations = Column(Text, nullable=True)
    suggestions      = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow)


class JobRole(Base):
    """Predefined job roles with required skills."""
    __tablename__ = "job_roles"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(255), nullable=False)
    required_skills = Column(Text, nullable=False)
    category        = Column(String(100), nullable=True)


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_job_roles()


def _seed_job_roles():
    import json
    db = SessionLocal()
    try:
        if db.query(JobRole).count() > 0:
            return
        job_roles = [
            {"title": "Data Analyst",            "category": "Data",           "required_skills": ["python","sql","excel","data visualization","statistics","pandas","tableau","power bi"]},
            {"title": "Machine Learning Engineer","category": "AI/ML",          "required_skills": ["python","machine learning","tensorflow","pytorch","scikit-learn","deep learning","nlp","statistics"]},
            {"title": "Backend Developer",        "category": "Software",       "required_skills": ["python","java","node.js","rest api","sql","docker","git","postgresql"]},
            {"title": "Frontend Developer",       "category": "Software",       "required_skills": ["javascript","html","css","react","vue","typescript","git","responsive design"]},
            {"title": "Full Stack Developer",     "category": "Software",       "required_skills": ["javascript","python","react","node.js","sql","rest api","git","html","css"]},
            {"title": "Data Scientist",           "category": "Data",           "required_skills": ["python","r","machine learning","statistics","data visualization","sql","pandas","numpy","scikit-learn"]},
            {"title": "DevOps Engineer",          "category": "Infrastructure", "required_skills": ["docker","kubernetes","ci/cd","linux","aws","terraform","git","bash","jenkins"]},
            {"title": "Cloud Architect",          "category": "Infrastructure", "required_skills": ["aws","azure","gcp","cloud architecture","docker","kubernetes","terraform","networking"]},
            {"title": "AI Research Scientist",    "category": "AI/ML",          "required_skills": ["deep learning","pytorch","tensorflow","nlp","computer vision","python","mathematics","research"]},
            {"title": "Database Administrator",   "category": "Data",           "required_skills": ["sql","postgresql","mysql","mongodb","database design","performance tuning","backup","linux"]},
            {"title": "Cybersecurity Analyst",    "category": "Security",       "required_skills": ["network security","penetration testing","linux","python","firewalls","siem","vulnerability assessment"]},
            {"title": "Mobile Developer",         "category": "Software",       "required_skills": ["flutter","react native","swift","kotlin","android","ios","javascript","git"]},
        ]
        for role in job_roles:
            db.add(JobRole(title=role["title"], category=role["category"],
                           required_skills=json.dumps(role["required_skills"])))
        db.commit()
        print(f"✅ Seeded {len(job_roles)} job roles")
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()