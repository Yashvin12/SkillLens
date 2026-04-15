"""
NLP Skill Extraction Service — SkillLens v4
=============================================
Upgrades from v3:
  - Semantic alias resolution (AWS ↔ "Amazon Web Services", K8s ↔ Kubernetes, etc.)
  - calculate_skill_gap now uses alias-aware matching + TF-IDF soft-match fallback
  - extract_contextual_experience: maps each detected skill → the bullet point proving it
  - Verb analyser: flags weak passive verbs with strong alternatives
"""

import re
import json
from typing import List, Set, Dict, Tuple, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ─────────────────────────────────────────────────────────────────────────────
# Master skill dictionary
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

ALL_SKILLS: Set[str] = set()
for _skills in SKILL_DICTIONARY.values():
    ALL_SKILLS.update(_skills)

# ─────────────────────────────────────────────────────────────────────────────
# Semantic alias map  — canonical skill → list of known aliases / abbreviations
# This is the semantic layer: catches "Amazon Web Services" → "aws" etc.
# ─────────────────────────────────────────────────────────────────────────────
SKILL_ALIASES: Dict[str, List[str]] = {
    "aws":                          ["amazon web services", "amazon aws", "aws cloud",
                                     "ec2", "s3", "lambda", "cloudformation", "ecs", "eks"],
    "gcp":                          ["google cloud", "google cloud platform", "gcp cloud",
                                     "bigquery", "cloud run", "gke"],
    "azure":                        ["microsoft azure", "azure cloud", "ms azure",
                                     "azure devops", "azure functions"],
    "machine learning":             ["ml", "statistical learning", "predictive modeling",
                                     "supervised learning", "unsupervised learning"],
    "deep learning":                ["neural networks", "dl", "ann",
                                     "artificial neural network", "neural net"],
    "natural language processing":  ["nlp", "text mining", "text analytics",
                                     "language model", "computational linguistics"],
    "nlp":                          ["natural language processing", "text mining",
                                     "language model", "text analytics"],
    "kubernetes":                   ["k8s", "container orchestration", "kube"],
    "docker":                       ["containerization", "containerisation",
                                     "container", "dockerfile"],
    "ci/cd":                        ["continuous integration", "continuous delivery",
                                     "continuous deployment", "devops pipeline",
                                     "github actions", "gitlab ci", "circleci"],
    "rest api":                     ["restful api", "restful", "rest", "api development",
                                     "web api", "http api", "restful services"],
    "postgresql":                   ["postgres", "pg", "psql"],
    "mongodb":                      ["mongo", "document database", "nosql"],
    "javascript":                   ["js", "ecmascript", "es6", "es2015", "es2020"],
    "typescript":                   ["ts"],
    "python":                       ["py", "python3", "python 3", "python2"],
    "react":                        ["reactjs", "react.js", "react native web"],
    "node.js":                      ["nodejs", "node js", "node"],
    "tensorflow":                   ["tf", "tensorflow 2", "tf2"],
    "scikit-learn":                 ["sklearn", "scikit learn"],
    "pandas":                       ["pd", "dataframe"],
    "git":                          ["version control", "github", "gitlab", "bitbucket"],
    "linux":                        ["ubuntu", "centos", "debian", "unix", "bash scripting",
                                     "shell scripting"],
    "sql":                          ["structured query language", "relational database",
                                     "rdbms", "t-sql", "plsql", "pl/sql"],
    "data visualization":           ["data viz", "charting", "dashboards", "visualization"],
    "agile":                        ["scrum", "kanban", "sprint", "agile methodology"],
    "computer vision":              ["cv", "image processing", "object detection",
                                     "image recognition"],
    "power bi":                     ["powerbi", "power bi desktop"],
    "microsoft azure":              ["azure"],
    "c++":                          ["cpp", "c plus plus"],
    "c#":                           ["csharp", "c sharp", "dotnet", ".net"],
}

# Build reverse lookup: alias_text → canonical_skill
_ALIAS_TO_CANONICAL: Dict[str, str] = {}
for _canonical, _aliases in SKILL_ALIASES.items():
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical

# Similarity threshold for soft TF-IDF matching (0–1)
SOFT_MATCH_THRESHOLD = 0.72

# ─────────────────────────────────────────────────────────────────────────────
# Weak verb → strong alternatives  (used by /api/analyze-verbs)
# ─────────────────────────────────────────────────────────────────────────────
WEAK_VERB_MAP: Dict[str, List[str]] = {
    "helped":        ["led", "drove", "spearheaded", "orchestrated"],
    "worked":        ["built", "engineered", "developed", "delivered"],
    "assisted":      ["accelerated", "strengthened", "elevated", "boosted"],
    "involved":      ["executed", "implemented", "architected", "designed"],
    "responsible":   ["owned", "led", "directed", "managed"],
    "participated":  ["contributed", "collaborated", "co-developed", "co-built"],
    "handled":       ["executed", "resolved", "automated", "streamlined"],
    "used":          ["leveraged", "applied", "implemented", "deployed"],
    "did":           ["delivered", "achieved", "shipped", "built"],
    "was part of":   ["collaborated with", "co-built", "contributed to"],
    "performed":     ["executed", "engineered", "automated", "optimised"],
    "maintained":    ["owned", "improved", "modernised", "optimised"],
    "tested":        ["validated", "quality-assured", "automated testing for", "verified"],
    "supported":     ["enabled", "powered", "accelerated", "fortified"],
    "contributed":   ["delivered", "shipped", "engineered", "built"],
    "utilized":      ["leveraged", "deployed", "applied", "integrated"],
    "utilised":      ["leveraged", "deployed", "applied", "integrated"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Core extraction helpers
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _resolve_alias(term: str) -> str:
    """Return canonical skill name if term is a known alias, else return term unchanged."""
    return _ALIAS_TO_CANONICAL.get(term.lower(), term.lower())


def extract_skills(text: str) -> List[str]:
    """
    Extract skills using two-pass approach:
      Pass 1 — exact keyword match against ALL_SKILLS (fast path)
      Pass 2 — alias resolution: check every sentence fragment against SKILL_ALIASES
    Returns a deduplicated, sorted list of canonical skill names.
    """
    if not text:
        return []

    normalized = preprocess_text(text)
    found: Set[str] = set()

    # Pass 1: exact match
    for skill in ALL_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, normalized):
            found.add(skill)

    # Pass 2: alias resolution — tokenise into n-grams up to 4 words
    words = normalized.split()
    for n in range(1, 5):
        for i in range(len(words) - n + 1):
            phrase = ' '.join(words[i:i+n])
            canonical = _ALIAS_TO_CANONICAL.get(phrase)
            if canonical and canonical in ALL_SKILLS:
                found.add(canonical)

    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────────
# Semantic skill gap (alias-aware + TF-IDF soft fallback)
# ─────────────────────────────────────────────────────────────────────────────

def calculate_skill_gap(resume_skills: List[str], job_skills: List[str]) -> dict:
    """
    Three-tier matching:
      Tier 1 — exact string match
      Tier 2 — alias/synonym match  (aws ↔ amazon web services)
      Tier 3 — TF-IDF cosine soft match at threshold 0.72

    Returns matched_skills, missing_skills, extra_skills, match_score,
    and semantic_matches list showing which aliases triggered a match.
    """
    resume_set = set(s.lower() for s in resume_skills)
    job_set    = set(s.lower() for s in job_skills)

    matched:        List[str] = []
    semantic_pairs: List[dict] = []   # [{job_skill, resume_skill, match_type}]

    # Tier 1 + 2: exact and alias match
    for js in job_set:
        # Tier 1
        if js in resume_set:
            matched.append(js)
            continue
        # Tier 2: expand both sides through aliases
        js_canonical = _resolve_alias(js)
        matched_via_alias = False
        for rs in resume_set:
            rs_canonical = _resolve_alias(rs)
            if js_canonical == rs_canonical or js == rs_canonical or rs == js_canonical:
                matched.append(js)
                semantic_pairs.append({"job_skill": js, "resume_skill": rs, "match_type": "alias"})
                matched_via_alias = True
                break
        if matched_via_alias:
            continue

    matched_set = set(matched)
    still_missing = [js for js in job_set if js not in matched_set]

    # Tier 3: TF-IDF soft match for remaining unmatched job skills
    if still_missing and resume_set:
        try:
            all_terms  = list(resume_set) + list(still_missing)
            vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2, 4))
            tfidf      = vectorizer.fit_transform(all_terms)
            r_vecs     = tfidf[:len(resume_set)]
            j_vecs     = tfidf[len(resume_set):]
            sims       = cosine_similarity(j_vecs, r_vecs)

            soft_matched = set()
            for ji, js in enumerate(still_missing):
                best_idx  = int(np.argmax(sims[ji]))
                best_sim  = float(sims[ji][best_idx])
                if best_sim >= SOFT_MATCH_THRESHOLD:
                    best_rs = list(resume_set)[best_idx]
                    matched.append(js)
                    soft_matched.add(js)
                    semantic_pairs.append({
                        "job_skill":    js,
                        "resume_skill": best_rs,
                        "match_type":   "soft",
                        "confidence":   round(best_sim, 3),
                    })
            still_missing = [js for js in still_missing if js not in soft_matched]
        except Exception:
            pass  # TF-IDF failed gracefully — still_missing stays as-is

    extra_skills = sorted(resume_set - job_set)
    match_score  = round(len(matched) / max(len(job_set), 1) * 100, 2)

    return {
        "matched_skills":  sorted(matched),
        "missing_skills":  sorted(still_missing),
        "extra_skills":    extra_skills,
        "match_score":     match_score,
        "semantic_matches": semantic_pairs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Contextual experience extraction
# ─────────────────────────────────────────────────────────────────────────────

def _extract_bullets(text: str) -> List[str]:
    """Extract bullet-point lines from resume text."""
    bullets = []
    for line in text.split('\n'):
        stripped = line.strip()
        if re.match(r'^[-•·*▪▸]\s+', stripped) and len(stripped) > 15:
            bullets.append(re.sub(r'^[-•·*▪▸]\s+', '', stripped))
        elif re.match(r'^\d+\.\s+', stripped) and len(stripped) > 15:
            bullets.append(re.sub(r'^\d+\.\s+', '', stripped))
    return bullets


def extract_contextual_experience(resume_text: str, skills: List[str]) -> Dict[str, str]:
    """
    Map each detected skill to the strongest bullet point that proves it.

    Strategy:
      1. Pull all bullet points from the resume
      2. For each skill, find bullets that mention the skill OR any of its aliases
      3. If multiple bullets match, prefer the one with a metric (number/%)
      4. Falls back to sentences (non-bullets) if no bullets match

    Returns: { skill: "the sentence proving they used it" }
    """
    bullets  = _extract_bullets(resume_text)
    # Also use full sentences as fallback
    sentences = [s.strip() for s in re.split(r'[.!?\n]', resume_text)
                 if len(s.strip()) > 20]

    context: Dict[str, str] = {}
    metric_re = re.compile(r'\b\d+[\s]*(k|m|%|percent|x|times|users|ms|\+)\b', re.I)

    for skill in skills:
        skill_lower   = skill.lower()
        # Build search terms: canonical skill + all its aliases
        search_terms  = {skill_lower}
        for alias in SKILL_ALIASES.get(skill_lower, []):
            search_terms.add(alias.lower())
        # Also check reverse: if skill is itself an alias
        canonical = _ALIAS_TO_CANONICAL.get(skill_lower)
        if canonical:
            search_terms.add(canonical)
            for alias in SKILL_ALIASES.get(canonical, []):
                search_terms.add(alias.lower())

        def _score_line(line: str) -> Tuple[bool, int]:
            """Returns (matches, metric_bonus)."""
            line_lower = line.lower()
            matches    = any(re.search(r'\b' + re.escape(t) + r'\b', line_lower)
                             for t in search_terms)
            bonus = len(metric_re.findall(line)) if matches else 0
            return matches, bonus

        # Search bullets first (they're better evidence)
        best_line    = None
        best_bonus   = -1
        for line in bullets:
            hit, bonus = _score_line(line)
            if hit and bonus > best_bonus:
                best_line  = line
                best_bonus = bonus

        # Fallback to sentences
        if best_line is None:
            for line in sentences:
                hit, bonus = _score_line(line)
                if hit and bonus > best_bonus:
                    best_line  = line
                    best_bonus = bonus

        if best_line:
            context[skill] = best_line[:200]  # cap length

    return context


# ─────────────────────────────────────────────────────────────────────────────
# Verb analysis (for /api/analyze-verbs)
# ─────────────────────────────────────────────────────────────────────────────

def analyse_verbs(bullets: List[str]) -> List[dict]:
    """
    For each bullet point, identify weak passive verbs and suggest alternatives.
    Returns list of { original, weak_verbs: [{weak_verb, alternatives, position}], has_weak }.
    """
    results = []
    for bullet in bullets:
        weak_found = []
        for weak, alternatives in WEAK_VERB_MAP.items():
            pattern = r'(?i)\b' + re.escape(weak) + r'\b'
            match   = re.search(pattern, bullet)
            if match:
                weak_found.append({
                    "weak_verb":    weak,
                    "alternatives": alternatives,
                    "start":        match.start(),
                    "end":          match.end(),
                })
        results.append({
            "original":   bullet,
            "weak_verbs": weak_found,
            "has_weak":   len(weak_found) > 0,
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Skill categories (unchanged public API)
# ─────────────────────────────────────────────────────────────────────────────

def get_skill_categories(skills: List[str]) -> dict:
    categorized = {}
    for category, category_skills in SKILL_DICTIONARY.items():
        matched = [s for s in skills if s in category_skills]
        if matched:
            categorized[category] = matched
    return categorized