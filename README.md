# ◈ SkillLens — AI-Powered Resume Skill Gap Analyzer

A full-stack AI system that analyzes your resume against a job description, identifies skill gaps, calculates an ATS match score, recommends job roles, and suggests learning paths — all powered by NLP and machine learning.

---

## 📁 Project Structure

```
resume_analyzer/
│
├── backend/                      # FastAPI Python backend
│   ├── main.py                   # App entry point, CORS, router registration
│   ├── requirements.txt          # Python dependencies
│   │
│   ├── models/
│   │   └── database.py           # SQLAlchemy models + SQLite init + seeding
│   │
│   ├── routers/
│   │   ├── resume.py             # /api/resume — upload & parse
│   │   ├── jobs.py               # /api/jobs  — job description analysis
│   │   └── analysis.py           # /api/analysis — full skill gap pipeline
│   │
│   └── services/
│       ├── resume_parser.py      # PDF text extraction (PyMuPDF), section detection
│       ├── nlp_service.py        # Skill extraction via keyword matching
│       └── ml_service.py         # TF-IDF job matching, suggestions, resources
│
├── frontend/
│   ├── index.html                # Single-page application
│   ├── css/
│   │   └── style.css             # Dark editorial theme, responsive
│   └── js/
│       └── app.js                # API calls, Chart.js, DOM rendering
│
├── setup.sh                      # One-time backend setup script
├── run_backend.sh                # Start the FastAPI server
└── README.md                     # This file
```

---

## 🚀 Installation & Setup

### Prerequisites
- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **pip** (comes with Python)
- A modern web browser (Chrome, Firefox, Edge)

---

### Step 1 — Clone / Download the Project

```bash
# If using git:
git clone <your-repo-url>
cd resume_analyzer

# Or simply extract the ZIP and cd into the folder
```

---

### Step 2 — Install Backend Dependencies

**Option A: Using the setup script (recommended)**
```bash
chmod +x setup.sh run_backend.sh
./setup.sh
```

**Option B: Manual setup**
```bash
cd backend
python3 -m venv venv

# Activate virtual environment:
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt
```

---

### Step 3 — Start the Backend Server

```bash
# From the project root:
./run_backend.sh

# Or manually:
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

✅ Backend will start at: **http://localhost:8000**  
📄 Interactive API docs: **http://localhost:8000/docs**

---

### Step 4 — Open the Frontend

Simply open `frontend/index.html` in your browser:

```bash
# macOS:
open frontend/index.html

# Linux:
xdg-open frontend/index.html

# Windows:
start frontend/index.html

# Or: right-click index.html → Open with → Chrome
```

> 💡 No server needed for the frontend — it communicates with the FastAPI backend via fetch API.

---

## 🧪 Testing the System

### Method 1: Demo Mode (Fastest)
Click the **"Demo"** link in the navigation bar to load a pre-filled sample resume and job description instantly.

### Method 2: Upload a Real Resume
1. Click **"Browse files"** and select a PDF resume
2. Click **"Parse Resume"** — skills will be detected
3. Paste a job description in the text area
4. Click **"Run Full Analysis"**

### Method 3: API Testing (via Swagger UI)
1. Open http://localhost:8000/docs
2. Use the **POST /api/analysis/quick** endpoint to test without a PDF:

```json
{
  "resume_text": "Python, SQL, Machine Learning, TensorFlow, Docker, Git, REST API",
  "job_description": "Looking for Data Scientist with Python, TensorFlow, scikit-learn, deep learning, statistics, SQL, AWS experience."
}
```

### Method 4: cURL
```bash
# Upload a resume PDF
curl -X POST "http://localhost:8000/api/resume/upload" \
  -F "file=@your_resume.pdf"

# Run quick analysis
curl -X POST "http://localhost:8000/api/analysis/quick" \
  -H "Content-Type: application/json" \
  -d '{"resume_text": "Python, SQL, Docker", "job_description": "Need Python, ML, TensorFlow, Docker"}'
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 📄 Resume Parsing | PDF text extraction using PyMuPDF |
| 🧠 NLP Skill Detection | Keyword-based extraction from 200+ skills |
| 🎯 Skill Gap Analysis | Compare resume vs job description |
| 📊 ATS Score | Match percentage with letter grade |
| 💼 Job Recommendations | TF-IDF + cosine similarity ranking |
| 📋 Resume Suggestions | Actionable improvement tips |
| 📚 Learning Resources | Curated Coursera/Udemy/YouTube links |
| 📈 Charts | Doughnut, bar, and gauge via Chart.js |
| 🗄️ History | SQLite persistence of past analyses |
| ⬇️ Export | Download analysis as .txt report |

---

## 🛠️ Technologies Used

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python) |
| Text Extraction | PyMuPDF (fitz) |
| NLP | Regex + keyword dictionary |
| ML/Recommendations | scikit-learn (TF-IDF + cosine similarity) |
| Database | SQLite + SQLAlchemy ORM |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| Charts | Chart.js 4.x |
| Fonts | Google Fonts (Syne + DM Sans) |

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resume/upload` | Upload PDF resume |
| GET | `/api/resume/{id}` | Get resume analysis |
| POST | `/api/jobs/analyze` | Analyze job description |
| GET | `/api/jobs/roles` | List all job roles |
| POST | `/api/analysis/full` | Full pipeline analysis |
| POST | `/api/analysis/quick` | Quick analysis (text only) |
| GET | `/api/analysis/history` | Recent analyses |

---

## 🔧 Troubleshooting

**Backend won't start?**
- Make sure port 8000 is free: `lsof -i :8000`
- Ensure Python 3.10+ is installed: `python3 --version`
- Activate the virtual environment before running uvicorn

**Frontend can't connect to backend?**
- Ensure the backend is running at http://localhost:8000
- Check browser console for CORS errors
- Verify `API_BASE` in `frontend/js/app.js` matches the backend URL

**"No skills found" in resume?**
- Ensure the PDF is text-based (not scanned image)
- Try the Demo mode to verify the pipeline works

**PDF upload fails?**
- Maximum file size: 10MB
- Only `.pdf` files are accepted
- The PDF must contain selectable text

---

## 👤 Project Info

**Project**: AI-Powered Resume Skill Gap Analyzer and Career Recommendation System  
**Domain**: Artificial Intelligence, Natural Language Processing, Web Development  
**Stack**: FastAPI · scikit-learn · PyMuPDF · SQLite · Chart.js  

---

*Built with ◈ SkillLens*
# ◈ SkillLens v3 — AI Resume Skill Gap Analyzer

## What's Fixed & New in v3

### 🐛 Bug Fixed: Profile Logout
**Before (broken):** Clicking the user pill immediately called `Auth.clear()` — logging the user out.  
**After (fixed):** The pill opens a **dropdown** with three distinct actions:
- **My Profile** → navigates to `profile.html` (token untouched)
- **Settings** → navigates to `profile.html` (token untouched)  
- **Logout** → calls `Auth.logout()` which clears token then redirects to `login.html`

### ✨ New Features
| Feature | File |
|---|---|
| Profile page with 4 tabs | `frontend/pages/profile.html` |
| Edit name / email | `PUT /user/update-profile` |
| Change password (bcrypt) | `POST /user/change-password` |
| Dark / Light mode toggle | `js/theme.js` + `css/profile.css` |
| Language & layout preferences | `PUT /user/preferences` |
| Notification toggles | `PUT /user/preferences` |
| Full analysis history table | `GET /user/history` |
| Download history report | client-side TXT export |
| Clear all history | `DELETE /user/history` |
| UserPreferences DB model | `models/database.py` |
| Dynamic landing nav (auth-aware) | `frontend/index.html` |

---

## Project Structure

```
skilllens_v3/
├── backend/
│   ├── main.py                    ← v3: registers /user router
│   ├── requirements.txt
│   ├── models/
│   │   └── database.py            ← v3: adds UserPreferences model
│   ├── routers/
│   │   ├── auth.py                ← unchanged from v2
│   │   ├── resume.py              ← unchanged from v2
│   │   ├── jobs.py                ← unchanged from v2
│   │   ├── analysis.py            ← unchanged from v2
│   │   └── user.py                ← NEW: profile/settings/history APIs
│   └── services/
│       ├── auth_service.py        ← unchanged
│       ├── nlp_service.py         ← unchanged
│       ├── ml_service.py          ← unchanged
│       └── resume_parser.py       ← unchanged
│
└── frontend/
    ├── index.html                 ← v3: auth-aware nav
    ├── css/
    │   ├── global.css             ← v3: light-mode vars + dropdown styles
    │   ├── dashboard.css          ← unchanged from v2
    │   ├── landing.css            ← unchanged from v2
    │   ├── auth.css               ← unchanged from v2
    │   └── profile.css            ← NEW: profile page + light mode
    ├── js/
    │   ├── api.js                 ← v3: /user methods + Auth.logout()
    │   ├── dashboard.js           ← v3: fixed dropdown, profile nav
    │   ├── theme.js               ← NEW: dark/light mode manager
    │   ├── profile.js             ← NEW: full profile page logic
    │   ├── auth.js                ← unchanged from v2
    │   └── toast.js               ← unchanged from v2
    └── pages/
        ├── dashboard.html         ← v3: fixed dropdown in topbar
        ├── profile.html           ← NEW: full profile & settings page
        ├── login.html             ← unchanged from v2
        └── signup.html            ← unchanged from v2
```

---

## Quick Start

```bash
# 1. Install dependencies (once)
chmod +x setup.sh && ./setup.sh

# 2. Start the API
chmod +x run.sh && ./run.sh
# → http://localhost:8000   (API)
# → http://localhost:8000/docs  (Swagger UI)

# 3. Open the frontend
open frontend/index.html
```

---

## New API Endpoints (v3)

All require `Authorization: Bearer <token>`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/user/profile` | Full profile + preferences + stats + recent history |
| PUT | `/user/update-profile` | Update name and/or email |
| POST | `/user/change-password` | Verify current pw, set new bcrypt hash |
| GET | `/user/preferences` | Get theme/language/layout/notifications |
| PUT | `/user/preferences` | Save preferences |
| GET | `/user/history` | Full analysis history |
| DELETE | `/user/history` | Clear all history |

---

## Theme System

`theme.js` is loaded **before** body content on every page to prevent flash.

```js
Theme.set('dark')    // switch to dark
Theme.set('light')   // switch to light
Theme.toggle()       // flip current
Theme.get()          // → 'dark' | 'light'
Theme.sync(prefs)    // sync from backend preferences
```

Preference stored in `localStorage('sl_theme')` and persisted to database via `PUT /user/preferences`.