"""
AI-Powered Resume Skill Gap Analyzer — SkillLens v3
=====================================================
Added: /user router for profile, settings, history management.
All existing /api/* and /auth/* routes preserved unchanged.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routers import resume, jobs, analysis, auth, user
from models.database import init_db
#from routers.user import router as user_router
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="AI Resume Skill Gap Analyzer",
    description="Analyse resumes, identify skill gaps, and get career recommendations",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    # 🚩 ALLOW ALL ORIGINS FOR DEPLOYMENT (Replace with your Vercel URL later for security)
    allow_origins=["https://skill-lens-gamma.vercel.app/"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routes — UNTOUCHED
app.include_router(auth.router,   prefix="/auth",       tags=["Authentication"])
app.include_router(resume.router, prefix="/api/resume", tags=["Resume"])
app.include_router(jobs.router,   prefix="/api/jobs",   tags=["Jobs"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
#app.include_router(user.router, prefix="/user") # <-- Prefix #2

# New in v3 — /user/* prefix matches the api.js client
app.include_router(user.router, prefix="/user", tags=["User Settings"])

@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Database ready (v3)")
    print("🚀 SkillLens is running!")


@app.get("/")
async def root():
    return {"message": "SkillLens API v3", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "3.0.0"}

#app.mount("/img", StaticFiles(directory="../frontend/img"), name="img")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
