#!/bin/bash
# SkillLens v3 — Start backend
cd "$(dirname "$0")/backend"
source venv/bin/activate
echo "🚀 SkillLens v3 API → http://localhost:8000"
echo "📄 Docs           → http://localhost:8000/docs"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload