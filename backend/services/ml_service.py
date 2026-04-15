"""
ML Service — SkillLens
=======================
Job recommendations (TF-IDF + cosine similarity) and learning resources.

Course data lives in courses.json — edit that file to add/update courses.
No API keys required. Optional Coursera public API fallback for uncatalogued skills.
"""

import json
import re
import threading
from pathlib import Path
from typing import List, Dict, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from dotenv import load_dotenv
load_dotenv()

# ── Load course catalogue from JSON (once at startup) ────────────────────────
_CATALOGUE_PATH = Path(__file__).parent / "courses.json"

def _load_catalogue() -> dict:
    try:
        with open(_CATALOGUE_PATH, encoding="utf-8") as f:
            return json.load(f).get("skills", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[ml_service] Warning: could not load courses.json — {e}")
        return {}

_CATALOGUE: dict = _load_catalogue()

# ── In-memory cache for Coursera API fallback results ────────────────────────
# Populated lazily; persists for the lifetime of the server process.
_coursera_cache: Dict[str, list] = {}
_cache_lock = threading.Lock()

DEFAULT_FALLBACK = [
    {
        "platform": "Coursera",
        "course":   "Search this skill on Coursera",
        "url":      "https://www.coursera.org/search?query=",
        "cost":     "freemium",
        "rating":   0,
        "best":     False,
    },
    {
        "platform": "freeCodeCamp",
        "course":   "Search tutorials on YouTube",
        "url":      "https://www.youtube.com/results?search_query=",
        "cost":     "free",
        "rating":   0,
        "best":     False,
    },
]


def _coursera_api_lookup(skill: str) -> Optional[list]:
    """
    Hit Coursera's free public REST API (no key needed) to find real courses.
    Returns a list of course dicts, or None if the request fails.
    Responses are cached in memory for the server's lifetime.
    """
    with _cache_lock:
        if skill in _coursera_cache:
            return _coursera_cache[skill]

    try:
        import requests
        resp = requests.get(
            "https://api.coursera.org/api/courses.v1",
            params={
                "q":      "search",
                "query":  skill,
                "fields": "name,slug,description",
                "limit":  3,
            },
            timeout=4,
        )
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
        results = [
            {
                "platform": "Coursera",
                "course":   el["name"],
                "url":      f"https://www.coursera.org/learn/{el['slug']}",
                "cost":     "freemium",
                "rating":   0,
                "best":     i == 0,
            }
            for i, el in enumerate(elements)
            if el.get("slug")
        ]
        if results:
            with _cache_lock:
                _coursera_cache[skill] = results
            return results
    except Exception:
        pass  # network unavailable or API changed — fall through to default
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def get_learning_resources(missing_skills: List[str]) -> Dict[str, dict]:
    """
    Return curated learning resources for each missing skill.

    Lookup order:
      1. courses.json  — curated, always available, no network needed
      2. Coursera API  — free public API, no key, called lazily and cached
      3. DEFAULT_FALLBACK — plain search links, always works
    """
    resources = {}

    for skill in missing_skills[:12]:
        skill_key = skill.lower()
        entry = _CATALOGUE.get(skill_key)

        if entry:
            resources[skill] = {
                "description": entry.get("description", f"Learn {skill} to strengthen your profile."),
                "level":       entry.get("level",       "Intermediate"),
                "hours":       entry.get("hours",       "20-40 hrs"),
                "courses":     entry.get("courses",     []),
            }
        else:
            api_courses = _coursera_api_lookup(skill_key)
            resources[skill] = {
                "description": f"Build proficiency in {skill} to strengthen your candidacy.",
                "level":       "Intermediate",
                "hours":       "20-40 hrs",
                "courses":     api_courses if api_courses else DEFAULT_FALLBACK,
            }

    return resources


# ── Job recommendation (TF-IDF + cosine similarity) ─────────────────────────


def recommend_jobs(resume_skills: List[str], db_session) -> List[dict]:
    from models.database import JobRole

    if not resume_skills:
        return []

    job_roles = db_session.query(JobRole).all()
    if not job_roles:
        return []

    # ✅ FIX: Keep skills as strict, separate lists (lowercased for perfect matching)
    candidate_list = [s.strip().lower() for s in resume_skills]
    job_lists, job_meta = [], []

    for role in job_roles:
        required = json.loads(role.required_skills)
        # Keep job requirements as a strict list too
        job_lists.append([s.strip().lower() for s in required])
        
        job_meta.append({
            "id":              role.id,
            "title":           role.title,
            "category":        role.category,
            "required_skills": required,
        })

    # The corpus is now a list of lists, not a list of strings
    corpus = [candidate_list] + job_lists
    
    # ✅ FIX: "analyzer=lambda x: x" tells the AI to stop guessing and just use our exact lists!
    vectorizer = TfidfVectorizer(analyzer=lambda x: x)
    tfidf      = vectorizer.fit_transform(corpus)
    sims       = cosine_similarity(tfidf[0], tfidf[1:])[0]

    recommendations = []
    for idx, score in enumerate(sims):
        meta         = job_meta[idx]
        resume_set   = set(candidate_list)
        required_set = set(job_lists[idx])
        
        # We also pass the original casing back for the UI
        recommendations.append({
            "title":            meta["title"],
            "category":         meta["category"],
            "similarity_score": round(float(score) * 100, 1),
            "matching_skills":  sorted(list(set(resume_skills) & set(meta["required_skills"]))),
            "missing_skills":   sorted(list(set(meta["required_skills"]) - set(resume_skills))),
            "required_skills":  meta["required_skills"],
        })

    recommendations.sort(key=lambda x: x["similarity_score"], reverse=True)
    return recommendations[:5]


# ── Personalised suggestions engine ──────────────────────────────────────────

# Role-skill profiles: what every role MUST have vs nice-to-have
_ROLE_PROFILES = {
    "data analyst": {
        "must": ["sql","pandas","excel","data visualization","statistics","python"],
        "nice": ["tableau","power bi","numpy","matplotlib","seaborn"],
        "interview_focus": "SQL queries, data cleaning, basic statistics, and storytelling with data",
    },
    "data scientist": {
        "must": ["python","machine learning","statistics","pandas","scikit-learn","sql"],
        "nice": ["deep learning","spark","tensorflow","feature engineering","data visualization"],
        "interview_focus": "ML model evaluation, feature engineering, statistics, and Python coding",
    },
    "machine learning engineer": {
        "must": ["python","machine learning","tensorflow","pytorch","scikit-learn","docker"],
        "nice": ["kubernetes","mlops","feature engineering","model deployment","aws"],
        "interview_focus": "ML system design, model serving, Python coding, and production deployment",
    },
    "backend developer": {
        "must": ["python","rest api","sql","git","docker"],
        "nice": ["kubernetes","redis","microservices","postgresql","ci/cd"],
        "interview_focus": "system design, API design, database queries, and coding challenges",
    },
    "frontend developer": {
        "must": ["javascript","react","html","css","typescript","git"],
        "nice": ["vue","next.js","webpack","figma","jest"],
        "interview_focus": "UI component design, browser performance, JavaScript fundamentals, and CSS layout",
    },
    "full stack developer": {
        "must": ["javascript","react","node.js","sql","git","html","css"],
        "nice": ["docker","typescript","rest api","postgresql","redis"],
        "interview_focus": "full request lifecycle, database design, API integration, and system design",
    },
    "devops engineer": {
        "must": ["docker","kubernetes","ci/cd","linux","aws","git"],
        "nice": ["terraform","ansible","jenkins","bash"],
        "interview_focus": "system reliability, CI/CD pipelines, container orchestration, and cloud infrastructure",
    },
    "cloud architect": {
        "must": ["aws","azure","gcp","terraform","docker"],
        "nice": ["kubernetes","microservices","security"],
        "interview_focus": "cloud-native design, high availability, cost optimisation, and security architecture",
    },
    "ai research scientist": {
        "must": ["python","pytorch","deep learning","mathematics","nlp","tensorflow"],
        "nice": ["computer vision","research"],
        "interview_focus": "ML theory, paper reading, experimental design, and mathematical reasoning",
    },
    "mobile developer": {
        "must": ["flutter","react native","kotlin","swift","git"],
        "nice": ["firebase","android","ios","rest api"],
        "interview_focus": "app lifecycle, state management, performance profiling, and platform APIs",
    },
    "cybersecurity analyst": {
        "must": ["network security","linux","penetration testing","python"],
        "nice": ["siem","firewalls","vulnerability assessment","encryption"],
        "interview_focus": "threat modelling, incident response, network protocols, and scripting for automation",
    },
    "database administrator": {
        "must": ["sql","postgresql","mysql","mongodb","linux"],
        "nice": ["redis","performance tuning","backup"],
        "interview_focus": "query optimisation, indexing strategies, backup/recovery, and replication",
    },
}

# Per-skill: why it matters for the role (interviewer-grade explanation)
_SKILL_CONTEXT = {
    "pandas":               "Analysts use Pandas every day for data wrangling — interviewers ask you to clean messy dataframes on the spot",
    "sql":                  "SQL is tested in almost every data/backend interview — window functions and JOINs are the most common questions",
    "statistics":           "Hypothesis testing and confidence intervals appear in every Data Analyst/Scientist interview round",
    "tableau":              "Tableau is a hard requirement in 60%+ of Data Analyst postings — a dashboard screenshot goes straight to a recruiter's shortlist",
    "power bi":             "Power BI dominates enterprise BI tooling — add it alongside Tableau to cover both ecosystems",
    "tensorflow":           "TensorFlow deployments are a standard production requirement for ML Engineer roles — PyTorch alone is not enough for many companies",
    "pytorch":              "PyTorch is now the dominant research and production framework — essential for any ML/AI role",
    "scikit-learn":         "Scikit-learn is the baseline ML library — if it's missing, reviewers will question your ML fundamentals",
    "docker":               "Docker is non-negotiable for backend/ML/DevOps roles — containerisation knowledge is assumed from year 2 onwards",
    "kubernetes":           "Kubernetes is required for senior backend and DevOps roles — even basic knowledge of Deployments and Services is a differentiator",
    "aws":                  "AWS is listed in 55%+ of tech job postings — the Solutions Architect Associate cert is a high-ROI addition",
    "ci/cd":                "CI/CD pipelines are expected in any DevOps or backend role — no pipeline knowledge signals you work alone",
    "react":                "React dominates frontend postings — a deployed project, not just a tutorial, separates candidates",
    "typescript":           "TypeScript is the default for production React/Node codebases — listing only JavaScript signals unfamiliarity with modern frontend",
    "machine learning":     "Generic 'machine learning' is weak — replace it with the specific algorithms and frameworks you've used",
    "deep learning":        "Deep learning without a project is noise — add a project showing you've trained a real neural network",
    "nlp":                  "NLP without a library name is vague — mention spaCy, Hugging Face Transformers, or NLTK specifically",
    "terraform":            "Terraform is the IaC standard — even a small AWS module on GitHub shows more than a certification alone",
    "linux":                "Linux proficiency is assumed in backend/DevOps roles — add specific tools (systemd, cron, iptables) to your bullets",
    "git":                  "Git is table stakes — what matters is a public GitHub profile with consistent commit history",
    "data visualization":   "Visualisation without a tool name is empty — specify matplotlib, seaborn, Plotly, or a BI tool",
    "rest api":             "REST API design is a core backend skill — mention HTTP methods, status codes, and auth (JWT/OAuth) in bullets",
    "microservices":        "Microservices architecture is expected at senior level — a demo repo with 2–3 services communicating shows tradeoff awareness",
    "redis":                "Redis caching is a quick differentiator — document the latency improvement in your project description",
    "feature engineering":  "Feature engineering is where most ML interview questions live — document your feature decisions in project descriptions",
    "spark":                "Spark separates data scientists who work at scale from those who only use Pandas — even one PySpark project matters",
}

# Project templates per role — (skill_trigger, full project description)
_PROJECT_TEMPLATES = {
    "data analyst": [
        ("pandas",             "End-to-End Sales Analysis: Load a Kaggle retail dataset into PostgreSQL, query with SQL, clean with Pandas, export a pivot-table report. Mirrors a real analyst workflow recruiters recognise."),
        ("tableau",            "Interactive Revenue Dashboard in Tableau Public: connect to a public finance dataset, build KPI cards, trend lines, and a regional map. Publish the link — recruiters click it in 30 seconds."),
        ("power bi",           "Power BI Sales Dashboard: import a retail dataset, model relationships, build slicers and drill-throughs. Upload the .pbix to GitHub."),
        ("statistics",         "A/B Test Analysis in Python: simulate a website experiment, run t-tests and chi-square tests, report p-values and effect sizes. A 1-page findings notebook shows statistical maturity."),
        ("data visualization", "Storytelling Dashboard with Plotly Dash: convert a static dataset into an interactive web app with dropdowns and date filters. Deploy free on Render."),
    ],
    "data scientist": [
        ("scikit-learn",       "End-to-End Classification Pipeline: EDA → feature engineering → model comparison (LR, RF, XGBoost) → SHAP explanations → model card. Post the Kaggle notebook."),
        ("machine learning",   "Kaggle Competition Submission: join an active tabular competition, reach top 30%, write a post-mortem on your feature engineering. The public leaderboard rank is proof."),
        ("deep learning",      "Image Classifier with Transfer Learning: fine-tune ResNet-50 on a custom dataset (100+ images), wrap in a Flask API, deploy to Hugging Face Spaces for free."),
        ("spark",              "Large-Scale Data Pipeline: process a 1 GB+ public dataset with PySpark on Colab, compare performance with Pandas, document the speedup."),
    ],
    "machine learning engineer": [
        ("tensorflow",         "Production ML API: train a TensorFlow model, export as SavedModel, serve via FastAPI with /predict endpoint, containerise with Docker, deploy to AWS Lambda. Full production stack in one repo."),
        ("pytorch",            "Fine-Tuned Transformer: fine-tune DistilBERT on a text classification task, expose via REST API, add a simple frontend. Shows modern NLP and deployment together."),
        ("mlops",              "MLflow Experiment Tracker: instrument an existing training script with MLflow, log hyperparameters and metrics, build a comparison UI. Shows you care about reproducibility."),
        ("kubernetes",         "Kubernetes ML Deployment: deploy a model server on Minikube with HPA — scales under load, shows production ML awareness."),
    ],
    "backend developer": [
        ("rest api",           "Production REST API with FastAPI: JWT auth, PostgreSQL with Alembic migrations, rate limiting with Redis, full pytest suite. Deploy to Railway and link the live URL."),
        ("microservices",      "Microservices Demo: split auth, products, and orders into 3 FastAPI services, add an Nginx gateway, wire with Docker Compose. Commit all manifests."),
        ("redis",              "Cached & Rate-Limited API: add Redis cache-aside pattern and sliding-window rate limiting to an existing API. Benchmark and document the latency improvement in the README."),
        ("ci/cd",              "GitHub Actions Pipeline: lint → type-check → test → build Docker image → push to GHCR → deploy to Render on every PR merge."),
    ],
    "frontend developer": [
        ("react",              "Full-Stack React App: React + TypeScript + Zustand + React Query, deployed to Vercel. Shows the modern frontend stack end-to-end."),
        ("typescript",         "Refactor a JS Project to TypeScript: convert an existing project, add strict tsconfig, fix all type errors. The diff on GitHub shows TypeScript discipline."),
        ("next.js",            "SEO-Optimised Next.js Blog: markdown-based blog with SSG, dynamic routes, image optimisation, and a perfect Lighthouse score. Deploy to Vercel."),
    ],
    "devops engineer": [
        ("kubernetes",         "Local Kubernetes Cluster with Minikube: deploy a 3-tier app (React/FastAPI/Postgres) with Helm charts, HPA, rolling updates, and liveness probes. Commit all manifests."),
        ("terraform",          "AWS Infrastructure as Code: provision VPC, EC2, RDS, S3, and IAM using Terraform with remote state in S3. One terraform apply spins up the full stack."),
        ("ci/cd",              "Full GitOps Pipeline: GitHub Actions → Docker → ECR → ArgoCD → EKS. Production-grade, zero-downtime deploys on every merge to main."),
    ],
    "cloud architect": [
        ("aws",                "Multi-Tier AWS Architecture: ALB → ECS Fargate → RDS Multi-AZ → ElastiCache → S3, all in Terraform with CloudWatch alarms. Attach the architecture diagram to your resume."),
        ("terraform",          "Reusable Terraform Module: build a vpc + eks + rds module. Shows you build infrastructure others can consume — a senior-level differentiator."),
    ],
    "mobile developer": [
        ("flutter",            "Cross-Platform App: Flutter + Firebase Auth + Firestore real-time feed + push notifications + Codemagic CI. Available on both TestFlight and Play Store."),
        ("react native",       "React Native + Expo offline-first notes app: SQLite local storage, dark mode, share extension. Expo Go QR in README — reviewers run it in 10 seconds."),
    ],
}

# Role-specific certification recommendations
_ROLE_CERTS = {
    "data analyst":              "Google Data Analytics Professional Certificate (Coursera, free to audit)",
    "machine learning engineer": "DeepLearning.AI TensorFlow Developer Certificate or AWS ML Specialty",
    "devops engineer":           "AWS Solutions Architect Associate or CKA (Certified Kubernetes Administrator)",
    "cloud architect":           "AWS Solutions Architect Professional or Google Cloud Professional Architect",
    "data scientist":            "DeepLearning.AI Machine Learning Specialization Certificate",
    "backend developer":         "AWS Developer Associate or Docker Certified Associate",
    "frontend developer":        "Meta Front-End Developer Professional Certificate (Coursera)",
    "cybersecurity analyst":     "CompTIA Security+ or Google Cybersecurity Professional Certificate",
}

_STRONG_VERBS = [
    "built","developed","designed","implemented","led","architected","optimised","optimized",
    "reduced","increased","improved","automated","created","launched","deployed","migrated",
    "scaled","engineered","delivered","achieved","spearheaded","mentored","refactored",
    "modernised","modernized","integrated","streamlined","established","drove","transformed",
]
_WEAK_VERBS = [
    "worked","helped","assisted","involved","responsible","participated","contributed",
    "supported","handled","did","used","performed","utilised","utilized",
]
_METRIC_RE = re.compile(
    r'\b\d+[\s]*(k|m|%|percent|x|times|users|customers|requests|ms|seconds|hours|days|billion|million|\+)\b',
    re.IGNORECASE,
)


def _analyse_resume(text: str) -> dict:
    t = text.lower()
    return {
        "bullet_count":  len(re.findall(r'[-•·]\s+\w', text)),
        "has_metrics":   bool(_METRIC_RE.search(text)),
        "strong_verbs":  sum(1 for v in _STRONG_VERBS if re.search(r'\b'+v+r'\b', t)),
        "weak_verbs":    [v for v in _WEAK_VERBS if re.search(r'\b'+v+r'\b', t)],
        "has_github":    bool(re.search(r'github\.com/', text, re.IGNORECASE)),
        "has_portfolio": bool(re.search(r'portfolio|\.dev\b|\.io\b|personal site', text, re.IGNORECASE)),
    }


def _infer_role(job_recommendations: list, job_skills: list) -> str:
    if job_recommendations:
        return job_recommendations[0].get("title", "").lower()
    job_set = set(s.lower() for s in job_skills)
    if len(job_set & {"tensorflow","pytorch","scikit-learn","machine learning","deep learning"}) >= 2:
        return "machine learning engineer"
    if len(job_set & {"pandas","tableau","power bi","statistics","data visualization"}) >= 2:
        return "data analyst"
    if len(job_set & {"docker","kubernetes","terraform","ci/cd","ansible"}) >= 2:
        return "devops engineer"
    if len(job_set & {"react","javascript","html","css","typescript"}) >= 2:
        return "frontend developer"
    return "backend developer"


def generate_resume_suggestions(
    resume_skills:       List[str],
    missing_skills:      List[str],
    sections:            dict,
    contact_info:        dict,
    job_skills:          List[str] = None,
    job_recommendations: list      = None,
    resume_text:         str       = "",
    match_score:         float     = 0.0,
) -> List[dict]:
    """
    Generate personalised, role-specific, prioritised suggestions.
    Returns a list of dicts: { priority, category, title, detail, action }
    """
    job_skills          = job_skills          or []
    job_recommendations = job_recommendations or []
    suggestions         = []

    # ── Context ───────────────────────────────────────────────────────────────
    target_role  = _infer_role(job_recommendations, job_skills)
    profile      = _ROLE_PROFILES.get(target_role, {})
    must_skills  = profile.get("must",  [])
    nice_skills  = profile.get("nice",  [])
    interview_f  = profile.get("interview_focus", "technical and behavioural questions")
    signals      = _analyse_resume(resume_text) if resume_text else {}
    role_display = target_role.title()
    resume_set   = set(s.lower() for s in resume_skills)
    missing_set  = set(s.lower() for s in missing_skills)

    critical_missing = [s for s in missing_skills if s.lower() in must_skills]
    useful_missing   = [s for s in missing_skills if s.lower() in nice_skills]

    # ── 🔴 Critical ───────────────────────────────────────────────────────────
    for skill in critical_missing[:3]:
        context = _SKILL_CONTEXT.get(skill.lower(),
                  f"'{skill}' is listed as a core requirement in most {role_display} postings")
        suggestions.append({
            "priority": "🔴 Critical",
            "category": "Skill Gap",
            "title":    f"Add {skill} — it is a hard requirement for {role_display}",
            "detail":   context,
            "action":   f"Learn {skill}, build one project with it, then add it to your Skills section and reference it in a project bullet.",
        })

    if match_score < 40 and job_skills:
        jd_missing = [s for s in job_skills if s.lower() not in resume_set][:5]
        if jd_missing:
            suggestions.append({
                "priority": "🔴 Critical",
                "category": "ATS Score",
                "title":    f"ATS score is {match_score:.0f}% — your resume will be filtered before a human reads it",
                "detail":   f"These exact keywords from the job description are absent from your resume: {', '.join(jd_missing)}.",
                "action":   "Add these terms verbatim in your Skills section. Weave the top 2 into your experience bullets.",
            })

    if resume_text and not signals.get("has_metrics") and sections.get("experience","").strip():
        suggestions.append({
            "priority": "🔴 Critical",
            "category": "Resume Quality",
            "title":    "No metrics found — your bullets describe tasks, not impact",
            "detail":   "Recruiters spend 7 seconds on a resume. Numbers force the eye to stop. Bullets without numbers are skipped.",
            "action":   (
                "Pick your 3 strongest bullets and add a number to each. "
                "E.g. 'Reduced API response time by 40%', 'Handled 10,000 daily active users', "
                "'Cut release time from 2 hours to 8 minutes with CI/CD automation'."
            ),
        })

    # ── 🟡 Skill Enhancements ─────────────────────────────────────────────────
    for skill in useful_missing[:2]:
        context = _SKILL_CONTEXT.get(skill.lower(),
                  f"Adds competitive edge for {role_display} applications")
        suggestions.append({
            "priority": "🟡 High",
            "category": "Skill Enhancement",
            "title":    f"Learn {skill} to strengthen your {role_display} profile",
            "detail":   context,
            "action":   f"Complete one focused course on {skill} (see Learning Path tab), then add it to a project bullet to prove it is not just a buzzword.",
        })

    weak_found = signals.get("weak_verbs", [])[:3]
    if resume_text and weak_found:
        suggestions.append({
            "priority": "🟡 High",
            "category": "Resume Language",
            "title":    f"Weak verbs found: '{', '.join(weak_found)}' — replace with impact language",
            "detail":   "Phrases like 'responsible for' or 'worked on' describe a job description, not your contribution.",
            "action":   (
                f"Replace '{weak_found[0]}' with 'Built', 'Engineered', 'Designed', or 'Delivered'. "
                "Every bullet should open with a strong past-tense verb and close with a measurable outcome."
            ),
        })

    if not signals.get("has_github"):
        suggestions.append({
            "priority": "🟡 High",
            "category": "Online Presence",
            "title":    "No GitHub link found — this is expected for every tech role",
            "detail":   f"For a {role_display} role, a public GitHub with real commits is stronger evidence than any bullet point.",
            "action":   "Add 'github.com/yourusername' to your resume header. Pin 2–3 relevant repos with README files.",
        })

    # ── 💼 Project Recommendations ────────────────────────────────────────────
    role_projects = _PROJECT_TEMPLATES.get(target_role, [])
    relevant = [(t, d) for t, d in role_projects
                if any(s.strip().lower() in missing_set or s.strip().lower() in resume_set
                       for s in t.split("+"))]
    if not relevant:
        relevant = role_projects[:2]

    for trigger, desc in relevant[:2]:
        skill_label = " + ".join(s.strip().title() for s in trigger.split("+"))
        suggestions.append({
            "priority": "🟡 High",
            "category": "Project Recommendation",
            "title":    f"Build: {skill_label} project for {role_display}",
            "detail":   desc,
            "action":   "Start this weekend. A working GitHub repo with a README beats a certification on a {role_display} resume.".format(role_display=role_display),
        })

    if not sections.get("projects","").strip():
        suggestions.append({
            "priority": "🟡 High",
            "category": "Resume Section",
            "title":    f"Projects section is missing — critical for a {role_display} role",
            "detail":   f"For {role_display} roles, projects are the primary proof of skills. Recruiters scroll directly to them.",
            "action":   "Add a Projects section with 2–3 entries: name, 1-line description, tech stack, GitHub/live link.",
        })

    # ── 📄 Resume Fixes ───────────────────────────────────────────────────────
    if not sections.get("summary","").strip():
        top3 = resume_skills[:3]
        first_gap = (critical_missing or missing_skills[:1] or ["advanced topics"])[0]
        suggestions.append({
            "priority": "🟢 Medium",
            "category": "Resume Fix",
            "title":    f"Add a {role_display}-specific summary at the top",
            "detail":   "Recruiters decide in 6 seconds. A summary anchors your profile to the target role before they read a single bullet.",
            "action":   (
                f"Write 2 lines: '[Your Name] is a {role_display} with hands-on experience in "
                f"{', '.join(top3)}. Currently building skills in {first_gap}.' "
                "No adjectives like 'passionate' — keep it factual."
            ),
        })

    cert_rec = _ROLE_CERTS.get(target_role, "a recognised certification from Coursera or Google")
    if not sections.get("certifications","").strip():
        suggestions.append({
            "priority": "🟢 Medium",
            "category": "Resume Fix",
            "title":    "No certifications found — add one to pass recruiter screening filters",
            "detail":   f"For {role_display}, {cert_rec} is widely recognised and fast to complete.",
            "action":   f"Enrol in {cert_rec}. The certificate badge on LinkedIn + resume is a quick credibility signal.",
        })

    if not contact_info.get("linkedin"):
        suggestions.append({
            "priority": "🟢 Medium",
            "category": "Resume Fix",
            "title":    "LinkedIn URL is missing from your resume header",
            "detail":   "70% of recruiters check LinkedIn before making a call. No link means many will not bother searching.",
            "action":   "Add 'linkedin.com/in/your-name' next to your email. Make sure your headline matches your target role title.",
        })

    suggestions.append({
        "priority": "🟢 Medium",
        "category": "Interview Prep",
        "title":    f"Start {role_display} interview prep — focus area: {interview_f}",
        "detail":   f"Your resume currently matches this role at {match_score:.0f}%. Each critical skill you add moves you 5–10% closer.",
        "action":   f"Practice 2 LeetCode mediums per day. Review {(must_skills[:2] or ['core concepts'])[0]} fundamentals. Book 2 mock interviews before applying.",
    })

    # ── 🚀 Quick Wins ─────────────────────────────────────────────────────────
    jd_missing_now = [s for s in job_skills if s.lower() not in resume_set][:4]
    if jd_missing_now:
        suggestions.append({
            "priority": "🚀 Quick Win",
            "category": "Quick Win",
            "title":    f"Add {len(jd_missing_now)} JD keywords to your Skills section right now",
            "detail":   f"These are in the job description but absent from your resume: {', '.join(jd_missing_now)}.",
            "action":   "Open your resume. Add them to Skills. Takes 5 minutes and immediately improves ATS matching.",
        })

    suggestions.append({
        "priority": "🚀 Quick Win",
        "category": "Quick Win",
        "title":    "Save your resume as a single-column ATS-safe PDF",
        "detail":   "Multi-column layouts and tables break most ATS parsers — your skills section may never be read.",
        "action":   "Use Google Docs 'Swiss' template or Overleaf 'AltaCV'. Font: Calibri 11pt. Margins 0.75in. Export as PDF.",
    })

    extra = [s for s in resume_skills if s.lower() not in set(j.lower() for j in job_skills)]
    if extra:
        suggestions.append({
            "priority": "🚀 Quick Win",
            "category": "Quick Win",
            "title":    f"You have {len(extra)} bonus skills not required by this JD — highlight them",
            "detail":   f"Skills like {', '.join(extra[:3])} show breadth beyond the minimum. Use them as differentiators.",
            "action":   "Add 'Also experienced with [skill1], [skill2]' at the end of your summary or as a separate line in Skills.",
        })

    return suggestions


# ── GitHub → Gemini Bullet Generator ─────────────────────────────────────────

def generate_github_bullets(repo_matches: dict) -> dict:
    """
    Use Google Gemini (gemini-1.5-flash) to write STAR-method resume bullets
    for each skill/repo combo discovered by the GitHub scraper.

    Parameters
    ----------
    repo_matches : dict
        Output of github_service.scan_github_for_skills():
        { "skill": [{ repo, url, language, description, stars, match_source }] }

    Returns
    -------
    dict
        { "skill": [ { "repo": "...", "url": "...", "bullet": "..." } ] }
    """
    import os

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    results: dict = {}

    for skill, repos in repo_matches.items():
        skill_bullets = []
        for repo_info in repos[:3]:  # max 3 repos per skill
            prompt = (
                f"You are an expert technical resume writer.\n\n"
                f"Write exactly ONE professional resume bullet point using the "
                f"STAR method (Situation, Task, Action, Result) that proves the "
                f"candidate has **{skill}** experience.\n\n"
                f"Context from their GitHub:\n"
                f"  • Repository slug: {repo_info['repo']}\n"
                f"  • Primary language: {repo_info['language']}\n"
                f"  • Description: {repo_info['description']}\n"
                f"  • Stars: {repo_info['stars']}\n\n"
                f"Rules:\n"
                f"1. First, convert the raw repository slug into a clean, properly "
                f"capitalized Project Name. For example: 'fastapi-gym-management' "
                f"becomes 'FastAPI Gym Management System', 'react-weather-app' "
                f"becomes 'React Weather App'. Use this clean name in the bullet.\n"
                f"2. Start with a strong past-tense action verb (e.g. Built, "
                f"Engineered, Designed, Deployed, Architected).\n"
                f"3. Mention the skill '{skill}' naturally in the bullet.\n"
                f"4. Include a plausible quantitative result where possible.\n"
                f"5. Keep it to ONE sentence, max 35 words.\n"
                f"6. Do NOT invent team sizes or company names.\n"
                f"7. Return ONLY the bullet text — no quotes, no numbering, "
                f"no extra commentary.\n"
            )

            # Also generate a clean project name from the repo slug
            raw_name = repo_info["repo"]
            clean_name = raw_name.replace("-", " ").replace("_", " ").title()

            try:
                response = model.generate_content(prompt)
                bullet_text = response.text.strip().strip('"').strip("'")
                # Remove any leading bullet characters
                if bullet_text.startswith(("- ", "• ", "· ", "* ")):
                    bullet_text = bullet_text[2:]
                skill_bullets.append({
                    "repo": repo_info["repo"],
                    "clean_name": clean_name,
                    "url": repo_info["url"],
                    "bullet": bullet_text,
                })
            except Exception as e:
                skill_bullets.append({
                    "repo": repo_info["repo"],
                    "clean_name": clean_name,
                    "url": repo_info["url"],
                    "bullet": f"[Generation failed: {str(e)[:80]}]",
                })

        if skill_bullets:
            results[skill] = skill_bullets

    return results