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

## 🛠️ Technologies Used

### ⚙️ Backend & Machine Learning
| Category | Technology |
| :--- | :--- |
| **Framework** | FastAPI (Python 3.10+) |
| **Server** | Uvicorn (ASGI) |
| **Security & Auth** | JWT (JSON Web Tokens), bcrypt (Passlib) |
| **Database & ORM** | SQLite + SQLAlchemy |
| **Data Validation** | Pydantic |
| **PDF Extraction** | PyMuPDF (fitz) |
| **AI & NLP Engine** | scikit-learn (TF-IDF + Cosine Similarity), Regular Expressions |

### 🎨 Frontend & User Interface
| Category | Technology |
| :--- | :--- |
| **Core Languages** | Vanilla JavaScript (ES6+), HTML5, CSS3 |
| **State Management**| Browser Local Storage API |
| **Data Visualization**| Chart.js 4.x |
| **Styling** | Custom CSS Variables (Dark/Light Theme compatibility) |
| **Typography** | Google Fonts (Syne + DM Sans) |

---

## 👤 Project Info

**Project**: AI-Powered Resume Skill Gap Analyzer and Career Recommendation System  
**Domain**: Artificial Intelligence, Natural Language Processing, Web Development  


---
