/**
 * SkillLens — AI Resume Analyzer
 * Frontend Application Logic
 * ============================================
 * Handles: file upload, API calls, result rendering, Chart.js visualizations
 */

const isDev = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = isDev ? "http://127.0.0.1:8000/api" : "https://skilllens-nnkt.onrender.com"; 

// ─── App State ───────────────────────────────────────────────────────────────
let state = {
  analysisId: null,
  resumeSkills: [],
  lastResults: null,
};

let skillMatchChart = null;
let categoryChart = null;
let gaugeChart = null;

// ─── DOM Ready ────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupDragAndDrop();
  setupCharCounter();
  checkBackendHealth();
});

// ─── Health Check ─────────────────────────────────────────────────────────────
async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE.replace("/api", "")}/health`);
    if (!res.ok) throw new Error();
    console.log("✅ Backend is healthy");
  } catch {
    showToast("⚠️ Backend not reachable. Make sure the FastAPI server is running on port 8000.", "error");
  }
}

// ─── File Handling ────────────────────────────────────────────────────────────
function setupDragAndDrop() {
  const zone = document.getElementById("uploadZone");
  const input = document.getElementById("resumeFile");

  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragover");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragover"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  });
  input.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) handleFileSelect(file);
  });
}

function handleFileSelect(file) {
  if (!file.name.endsWith(".pdf")) {
    showToast("Please upload a PDF file.", "error");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast("File exceeds 10MB limit.", "error");
    return;
  }

  // Show file preview
  document.getElementById("uploadZone").classList.add("hidden");
  const preview = document.getElementById("filePreview");
  preview.classList.remove("hidden");
  document.getElementById("fileName").textContent = file.name;
  document.getElementById("fileSize").textContent = formatFileSize(file.size);

  // Enable upload button
  const btn = document.getElementById("uploadBtn");
  btn.disabled = false;
  btn._file = file;  // attach file to button for retrieval
}

function removeFile() {
  document.getElementById("uploadZone").classList.remove("hidden");
  document.getElementById("filePreview").classList.add("hidden");
  document.getElementById("resumeFile").value = "";
  document.getElementById("uploadBtn").disabled = true;
  document.getElementById("analyzeBtn").disabled = true;
  state.analysisId = null;
}

// ─── Step 1: Upload Resume ────────────────────────────────────────────────────
async function uploadResume() {
  const btn = document.getElementById("uploadBtn");
  const file = btn._file;
  if (!file) return;

  setLoading(true, "Parsing resume PDF...");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/resume/upload`, {
      method: "POST",
      body: formData,
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Upload failed");

    state.analysisId = data.analysis_id;
    state.resumeSkills = data.detected_skills;

    // Show upload success feedback
    btn.innerHTML = `<span>✅ Resume Parsed (${data.skill_count} skills found)</span>`;
    btn.disabled = true;
    btn.style.background = "var(--green)";

    // Enable analyze button
    document.getElementById("analyzeBtn").disabled = false;
    showToast(`Found ${data.skill_count} skills in your resume!`, "success");

    console.log("Resume upload result:", data);
  } catch (err) {
    showToast("❌ Upload failed: " + err.message, "error");
  } finally {
    setLoading(false);
  }
}

// ─── Step 2: Full Analysis ─────────────────────────────────────────────────────
async function runAnalysis() {
  const jd = document.getElementById("jobDescription").value.trim();

  if (!state.analysisId) {
    showToast("Please upload your resume first.", "error");
    return;
  }
  if (!jd) {
    showToast("Please paste a job description.", "error");
    return;
  }
  if (jd.length < 50) {
    showToast("Job description seems too short. Please provide more details.", "error");
    return;
  }

  setLoading(true, "Running AI analysis...");

  try {
    const res = await fetch(`${API_BASE}/analysis/full`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        analysis_id: state.analysisId,
        job_description: jd,
      }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Analysis failed");

    state.lastResults = data;
    renderResults(data);
    showToast("Analysis complete!", "success");
  } catch (err) {
    showToast("❌ Analysis failed: " + err.message, "error");
  } finally {
    setLoading(false);
  }
}

// ─── Demo Mode ────────────────────────────────────────────────────────────────
async function showDemo() {
  const demoResume = `
    John Doe | johndoe@email.com | LinkedIn: linkedin.com/in/johndoe
    
    SUMMARY
    Software engineer with 3 years of experience in Python, JavaScript, and web development.
    
    EXPERIENCE
    Backend Developer – TechCorp (2021-Present)
    - Built REST APIs using Python and Flask
    - Managed PostgreSQL databases and wrote complex SQL queries
    - Deployed applications using Docker on AWS
    
    EDUCATION
    B.E. Computer Engineering – University of Pune (2021)
    
    SKILLS
    Python, JavaScript, HTML, CSS, SQL, PostgreSQL, Docker, Git, Flask, React, Linux, Pandas, NumPy
    
    PROJECTS
    - E-commerce API: REST API built with Python/Flask and PostgreSQL
    - Portfolio Website: React frontend with Node.js backend
  `;

  const demoJD = `
    We are looking for a Machine Learning Engineer to join our AI team.
    
    Requirements:
    - Strong proficiency in Python
    - Experience with machine learning frameworks: TensorFlow, PyTorch, scikit-learn
    - Knowledge of deep learning and neural networks
    - Familiarity with NLP techniques and libraries
    - Experience with data analysis: Pandas, NumPy, Matplotlib
    - Cloud platform experience: AWS or GCP
    - Docker and Kubernetes experience
    - SQL and database management skills
    - Strong understanding of statistics and mathematics
    - Version control with Git
  `;

  document.getElementById("jobDescription").value = demoJD;
  updateCharCount();
  setLoading(true, "Running demo analysis...");

  try {
    const res = await fetch(`${API_BASE}/analysis/quick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resume_text: demoResume, job_description: demoJD }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Demo failed");

    state.lastResults = data;
    renderResults(data);
    showToast("Demo loaded! This is a sample analysis.", "success");
  } catch (err) {
    showToast("❌ Demo failed: " + err.message, "error");
  } finally {
    setLoading(false);
  }
}

// ─── Render Results ───────────────────────────────────────────────────────────
function renderResults(data) {
  const section = document.getElementById("resultsSection");
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth" });

  // ATS Score
  document.getElementById("atsScore").textContent = `${data.match_score}%`;
  document.getElementById("atsVerdict").textContent = data.ats_label;

  // Update ATS banner color based on score
  const banner = document.getElementById("atsBanner");
  if (data.match_score >= 70) banner.style.borderColor = "var(--green)";
  else if (data.match_score >= 40) banner.style.borderColor = "var(--accent)";
  else banner.style.borderColor = "var(--red)";

  // Stat counters
  document.getElementById("matchedCount").textContent = data.skill_match_chart.matched;
  document.getElementById("missingCount").textContent = data.skill_match_chart.missing;
  document.getElementById("resumeSkillCount").textContent = data.skill_match_chart.total_resume_skills;
  document.getElementById("jobSkillCount").textContent = data.skill_match_chart.total_job_skills;

  // Charts
  renderGaugeChart(data.match_score);
  renderSkillMatchChart(data.skill_match_chart);
  renderCategoryChart(data.resume_skill_categories);

  // Skill lists
  renderSkillList("missingSkillsList", data.missing_skills, "missing");
  renderSkillList("matchedSkillsList", data.matched_skills, "matched");

  // Job recommendations
  renderJobRecommendations(data.job_recommendations);

  // Suggestions
  renderSuggestions(data.suggestions);

  // Learning resources
  renderLearningResources(data.learning_resources);
}

// ─── Chart.js: Gauge ──────────────────────────────────────────────────────────
function renderGaugeChart(score) {
  const ctx = document.getElementById("scoreGauge").getContext("2d");
  if (gaugeChart) gaugeChart.destroy();

  const remaining = 100 - score;
  const color = score >= 70 ? "#2ecc71" : score >= 40 ? "#f5a623" : "#e74c3c";

  gaugeChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [score, remaining],
        backgroundColor: [color, "#252b3b"],
        borderWidth: 0,
        circumference: 270,
        rotation: 225,
      }],
    },
    options: {
      responsive: true,
      cutout: "75%",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
    },
  });
}

// ─── Chart.js: Skill Match Doughnut ──────────────────────────────────────────
function renderSkillMatchChart(chartData) {
  const ctx = document.getElementById("skillMatchChart").getContext("2d");
  if (skillMatchChart) skillMatchChart.destroy();

  skillMatchChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Matched", "Missing", "Extra (bonus)"],
      datasets: [{
        data: [chartData.matched, chartData.missing, chartData.extra],
        backgroundColor: ["#2ecc71", "#e74c3c", "#3498db"],
        borderWidth: 2,
        borderColor: "#141720",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "60%",
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: "#8892a8", font: { size: 12 }, padding: 16 },
        },
      },
    },
  });
}

// ─── Chart.js: Category Radar / Bar ───────────────────────────────────────────
function renderCategoryChart(categories) {
  const ctx = document.getElementById("categoryChart").getContext("2d");
  if (categoryChart) categoryChart.destroy();

  if (!categories || Object.keys(categories).length === 0) {
    ctx.fillStyle = "#555f75";
    ctx.font = "14px DM Sans";
    ctx.textAlign = "center";
    ctx.fillText("No categorized skills found", 150, 110);
    return;
  }

  const labels = Object.keys(categories).map(k => k.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase()));
  const values = Object.values(categories).map(v => v.length);

  const colors = ["#f5a623", "#2ecc71", "#3498db", "#9b59b6", "#e74c3c", "#1abc9c", "#e67e22", "#34495e"];

  categoryChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Skills",
        data: values,
        backgroundColor: colors.slice(0, labels.length),
        borderRadius: 6,
        borderWidth: 0,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      indexAxis: "y",
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: {
          grid: { color: "#252b3b" },
          ticks: { color: "#8892a8", font: { size: 11 } },
        },
        y: {
          grid: { display: false },
          ticks: { color: "#8892a8", font: { size: 11 } },
        },
      },
    },
  });
}

// ─── Render Skill Tags ────────────────────────────────────────────────────────
function renderSkillList(containerId, skills, type) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  if (!skills || skills.length === 0) {
    container.innerHTML = `<p class="empty-state">${type === "missing" ? "No skill gaps — great match!" : "No matched skills detected."}</p>`;
    return;
  }

  skills.forEach((skill, i) => {
    const tag = document.createElement("span");
    tag.className = `skill-tag ${type}`;
    tag.textContent = (type === "missing" ? "✗ " : "✓ ") + skill;
    tag.style.animationDelay = `${i * 30}ms`;
    container.appendChild(tag);
  });
}

// ─── Render Job Recommendations ───────────────────────────────────────────────
function renderJobRecommendations(jobs) {
  const container = document.getElementById("jobRecommendations");
  container.innerHTML = "";

  if (!jobs || jobs.length === 0) {
    container.innerHTML = `<p class="empty-state">No recommendations available.</p>`;
    return;
  }

  jobs.forEach((job, idx) => {
    const card = document.createElement("div");
    card.className = "job-rec-card";
    card.style.animationDelay = `${idx * 80}ms`;

    const topSkills = (job.matching_skills || []).slice(0, 4)
      .map(s => `<span class="job-skill-chip">${s}</span>`).join("");

    card.innerHTML = `
      <div class="job-rec-rank">${String(idx + 1).padStart(2, "0")}</div>
      <div class="job-rec-info">
        <div class="job-rec-title">${job.title}</div>
        <div class="job-rec-category">${job.category}</div>
        <div class="job-rec-skills">${topSkills || "<span class='job-skill-chip'>—</span>"}</div>
      </div>
      <div class="job-rec-score-wrap">
        <div class="job-rec-score">${job.similarity_score}%</div>
        <div class="job-rec-score-label">match</div>
      </div>
    `;
    container.appendChild(card);
  });
}

// ─── Render Suggestions ───────────────────────────────────────────────────────
function renderSuggestions(suggestions) {
  const list = document.getElementById("suggestionsList");
  list.innerHTML = "";

  if (!suggestions || suggestions.length === 0) {
    list.innerHTML = `<p class="empty-state">No suggestions available.</p>`;
    return;
  }

  suggestions.forEach((s, i) => {
    const li = document.createElement("li");
    li.className = "suggestion-item";
    li.textContent = s;
    li.style.animationDelay = `${i * 60}ms`;
    list.appendChild(li);
  });
}

// ─── Render Learning Resources ────────────────────────────────────────────────
function renderLearningResources(resources) {
  const container = document.getElementById("learningResources");
  container.innerHTML = "";

  if (!resources || Object.keys(resources).length === 0) {
    container.innerHTML = `<p class="empty-state">No learning resources to suggest.</p>`;
    return;
  }

  Object.entries(resources).forEach(([skill, courses]) => {
    const group = document.createElement("div");
    group.className = "resource-group";
    group.innerHTML = `<div class="resource-skill-name">${skill}</div>`;

    const list = document.createElement("div");
    list.className = "resource-list";

    courses.forEach(course => {
      const item = document.createElement("a");
      item.className = "resource-item";
      item.href = course.url;
      item.target = "_blank";
      item.rel = "noopener noreferrer";
      item.innerHTML = `
        <span class="resource-platform">${course.platform}</span>
        <span class="resource-course">${course.course}</span>
        <span class="resource-arrow">↗</span>
      `;
      list.appendChild(item);
    });

    group.appendChild(list);
    container.appendChild(group);
  });
}

// ─── History ──────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE}/analysis/history`);
    const data = await res.json();

    const list = document.getElementById("historyList");
    if (!data.length) {
      list.innerHTML = `<p class="empty-state">No analyses yet.</p>`;
      return;
    }

    list.innerHTML = data.map(item => `
      <div class="history-item">
        <div>
          <strong>${item.filename}</strong>
          <div style="font-size:12px;color:var(--text-muted)">${item.detected_skills_count} skills · ${new Date(item.created_at).toLocaleDateString()}</div>
        </div>
        <div class="history-score">${item.match_score}%</div>
      </div>
    `).join("");
  } catch {
    document.getElementById("historyList").innerHTML = `<p class="empty-state">Could not load history.</p>`;
  }
}

document.getElementById("historyNavBtn")?.addEventListener("click", (e) => {
  e.preventDefault();
  const section = document.getElementById("history-section");
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth" });
  loadHistory();
});

// ─── Reset ────────────────────────────────────────────────────────────────────
function resetAll() {
  state = { analysisId: null, resumeSkills: [], lastResults: null };

  document.getElementById("resultsSection").classList.add("hidden");
  document.getElementById("uploadZone").classList.remove("hidden");
  document.getElementById("filePreview").classList.add("hidden");
  document.getElementById("resumeFile").value = "";
  document.getElementById("jobDescription").value = "";
  document.getElementById("charCount").textContent = "0 characters";

  const uploadBtn = document.getElementById("uploadBtn");
  uploadBtn.disabled = true;
  uploadBtn.style.background = "";
  uploadBtn.innerHTML = `<span>Parse Resume</span><span class="btn-arrow">→</span>`;
  document.getElementById("analyzeBtn").disabled = true;

  [skillMatchChart, categoryChart, gaugeChart].forEach(c => c?.destroy());
  skillMatchChart = categoryChart = gaugeChart = null;

  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ─── Export Results ───────────────────────────────────────────────────────────
function exportResults() {
  if (!state.lastResults) return;

  const d = state.lastResults;
  const txt = `
SkillLens — Resume Analysis Report
=====================================
ATS Match Score: ${d.match_score}% (${d.ats_label})

MATCHED SKILLS (${d.matched_skills.length}):
${d.matched_skills.join(", ")}

MISSING SKILLS (${d.missing_skills.length}):
${d.missing_skills.join(", ")}

JOB RECOMMENDATIONS:
${(d.job_recommendations || []).map((j, i) => `${i+1}. ${j.title} — ${j.similarity_score}% match`).join("\n")}

IMPROVEMENT SUGGESTIONS:
${(d.suggestions || []).join("\n")}

Generated by SkillLens on ${new Date().toLocaleDateString()}
  `.trim();

  const blob = new Blob([txt], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "skilllens-analysis.txt";
  a.click();
}

// ─── Utilities ────────────────────────────────────────────────────────────────
function setLoading(show, message = "") {
  const overlay = document.getElementById("loadingOverlay");
  if (show) {
    overlay.classList.remove("hidden");
    document.getElementById("loaderText").textContent = message;
  } else {
    overlay.classList.add("hidden");
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function setupCharCounter() {
  const jd = document.getElementById("jobDescription");
  const counter = document.getElementById("charCount");
  jd.addEventListener("input", updateCharCount);
}

function updateCharCount() {
  const jd = document.getElementById("jobDescription");
  const counter = document.getElementById("charCount");
  const len = jd.value.length;
  counter.textContent = `${len} characters`;
  if (len > 50 && state.analysisId) {
    document.getElementById("analyzeBtn").disabled = false;
  }
}

function showToast(message, type = "info") {
  // Remove existing toast
  const existing = document.getElementById("toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "toast";
  const bg = type === "error" ? "#e74c3c" : type === "success" ? "#2ecc71" : "#3498db";
  toast.style.cssText = `
    position: fixed; bottom: 30px; right: 30px; z-index: 9999;
    background: ${bg}; color: #fff; padding: 14px 20px;
    border-radius: 10px; font-size: 14px; font-weight: 500;
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
    animation: fadeIn 0.3s ease; max-width: 360px;
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
