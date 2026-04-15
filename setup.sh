#!/bin/bash
# SkillLens v3 — One-time setup
set -e
echo "╔══════════════════════════════════════════╗"
echo "║   SkillLens v3 Setup                     ║"
echo "╚══════════════════════════════════════════╝"
cd "$(dirname "$0")/backend"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo ""
echo "✅ Setup complete!"
echo "Run: ./run.sh to start the backend"
echo "Then open: frontend/index.html in your browser"
