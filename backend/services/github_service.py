"""
GitHub Service — SkillLens
===========================
Scans a user's public GitHub repos and matches them against a list of
missing skills (language, topics, description keywords).

No auth token required — uses the public GitHub REST API.
Rate-limit: 60 requests/hour per IP (unauthenticated).
"""

import requests
from typing import List, Dict

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 8  # seconds


def scan_github_for_skills(
    username: str,
    missing_skills: List[str],
) -> Dict[str, list]:
    """
    Fetch all public repos for *username* and check each repo's
    language, topics, and description for any of the *missing_skills*.

    Returns
    -------
    dict
        {
          "skill_name": [
            { "repo": "repo-name", "url": "html_url", "language": "Python",
              "description": "...", "stars": 12, "match_source": "language" },
            ...
          ],
          ...
        }
        Only skills with at least one matching repo are included.
    """

    # ── Fetch repos ──────────────────────────────────────────────────────
    url = f"{GITHUB_API}/users/{username}/repos"
    params = {"per_page": 100, "sort": "updated", "direction": "desc"}
    headers = {"Accept": "application/vnd.github+json"}

    resp = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)

    if resp.status_code == 404:
        raise ValueError(f"GitHub user '{username}' not found.")
    if resp.status_code == 403:
        raise ConnectionError("GitHub API rate limit exceeded. Try again in a few minutes.")
    resp.raise_for_status()

    repos = resp.json()
    if not isinstance(repos, list):
        raise ValueError("Unexpected response from GitHub API.")

    # ── Normalise skill names for matching ────────────────────────────────
    skill_variants: Dict[str, str] = {}  # lowercase variant → original skill
    for skill in missing_skills:
        low = skill.lower().strip()
        skill_variants[low] = skill
        # Common aliases
        if low == "react":
            skill_variants["reactjs"] = skill
            skill_variants["react.js"] = skill
        elif low == "node.js":
            skill_variants["nodejs"] = skill
            skill_variants["node"] = skill
        elif low == "typescript":
            skill_variants["ts"] = skill
        elif low == "javascript":
            skill_variants["js"] = skill
        elif low == "machine learning":
            skill_variants["ml"] = skill
            skill_variants["machinelearning"] = skill
        elif low == "deep learning":
            skill_variants["deeplearning"] = skill
            skill_variants["dl"] = skill
        elif low == "ci/cd":
            skill_variants["cicd"] = skill
            skill_variants["ci-cd"] = skill
            skill_variants["github-actions"] = skill

    # ── Scan repos ────────────────────────────────────────────────────────
    matches: Dict[str, list] = {}

    for repo in repos:
        if repo.get("fork"):
            continue  # skip forks — they don't prove personal work

        repo_lang = (repo.get("language") or "").lower()
        repo_topics = [t.lower() for t in (repo.get("topics") or [])]
        repo_desc = (repo.get("description") or "").lower()
        repo_name_lower = (repo.get("name") or "").lower()

        # Combine all searchable text
        searchable = set(repo_topics)
        searchable.add(repo_lang)
        searchable_text = f"{repo_desc} {repo_name_lower}"

        for variant, original_skill in skill_variants.items():
            found_via = None

            if variant in searchable:
                found_via = "topic" if variant in repo_topics else "language"
            elif variant in searchable_text:
                found_via = "description"

            if found_via:
                entry = {
                    "repo": repo.get("name", ""),
                    "url": repo.get("html_url", ""),
                    "language": repo.get("language") or "—",
                    "description": (repo.get("description") or "No description")[:120],
                    "stars": repo.get("stargazers_count", 0),
                    "match_source": found_via,
                }
                matches.setdefault(original_skill, [])
                # Avoid duplicates (same repo matched via multiple variants)
                if not any(m["repo"] == entry["repo"] for m in matches[original_skill]):
                    matches[original_skill].append(entry)

    # Sort each skill's repos by stars (descending) and limit to top 3
    for skill in matches:
        matches[skill] = sorted(matches[skill], key=lambda r: r["stars"], reverse=True)[:3]

    return matches
