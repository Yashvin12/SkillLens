/**
 * SkillLens Dashboard — v3
 * =========================
 * KEY FIX: user-pill click now opens a dropdown with separate
 *   "My Profile" → profile.html   (does NOT clear token)
 *   "Logout"     → clears token, goes to login.html
 *
 * All analysis, chart, history, and upload logic preserved from v2.
 */

const state = {
  analysisId: null,
  lastResult: null,
  charts: {},
};

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  Theme.init();
  setupUserDropdown();   // ← replaces the broken setupUserPill
  setupUploadZone();
  setupJDCounter();
  setupTabs();
  setupProfileTabs(); // <--- ADD THIS HERE!
  hydrateProfile();

  if (localStorage.getItem('sl_run_demo') === '1') {
    localStorage.removeItem('sl_run_demo');
    setTimeout(runDemo, 400);
  }
  if (Auth.isLoggedIn()) loadHistory();
});

// ── User Dropdown (FIXED — profile ≠ logout) ──────────────────────────────────
function setupUserDropdown() {
  const avatar  = document.getElementById('userAvatar');
  const nameEl  = document.getElementById('userName');
  const pill    = document.getElementById('userPill');
  const dropdown= document.getElementById('userDropdown');
  const user    = Auth.user();

  // FIX: Added 'user.name' check so it doesn't crash on undefined!
  if (user && user.name) {
    if (avatar) avatar.textContent = user.name.charAt(0).toUpperCase();
    if (nameEl) nameEl.textContent = user.name;
  } else if (user && user.email) {
    // Fallback if name is missing but email exists
    if (avatar) avatar.textContent = user.email.charAt(0).toUpperCase();
    if (nameEl) nameEl.textContent = user.email.split('@')[0];
  } else {
    if (avatar) avatar.textContent = '?';
    if (nameEl) nameEl.textContent = 'Guest';
  }

  // Toggle dropdown on pill click
  pill?.addEventListener('click', e => {
    e.stopPropagation();
    dropdown?.classList.toggle('hidden');
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', () => dropdown?.classList.add('hidden'));
  dropdown?.addEventListener('click', e => e.stopPropagation());

  // ✅ Profile — navigate WITHOUT clearing token
  document.getElementById('dropdownProfile')?.addEventListener('click', () => {
    window.location.href = 'profile.html';
  });

  // ✅ Logout — ONLY here do we call Auth.logout()
  document.getElementById('dropdownLogout')?.addEventListener('click', () => {
    Auth.logout('login.html');
  });
}

// ── Upload Zone ───────────────────────────────────────────────────────────────
function setupUploadZone() {
  const zone      = document.getElementById('uploadZone');
  const input     = document.getElementById('resumeFile');
  const uploadBtn = document.getElementById('uploadBtn');

  if (!zone || !input) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });
  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', e => { if (e.target.files[0]) handleFile(e.target.files[0]); });
  document.getElementById('removeFile')?.addEventListener('click', e => { e.stopPropagation(); resetFile(); });
  uploadBtn?.addEventListener('click', e => { e.stopPropagation(); uploadResume(); });
}

function handleFile(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) { Toast.error('Only PDF files accepted'); return; }
  if (file.size > 10 * 1024 * 1024) { Toast.error('File exceeds 10 MB limit'); return; }
  document.getElementById('uploadZone').querySelector('.upload-inner').classList.add('hidden');
  const preview = document.getElementById('filePreview');
  preview.classList.remove('hidden');
  document.getElementById('previewFileName').textContent = file.name;
  document.getElementById('previewFileSize').textContent = fmtSize(file.size);
  document.getElementById('uploadBtn').disabled = false;
  document.getElementById('uploadBtn')._file = file;
  state.analysisId = null;
  document.getElementById('analyzeBtn').disabled = true;
}

function resetFile() {
  document.getElementById('resumeFile').value = '';
  document.getElementById('filePreview').classList.add('hidden');
  document.getElementById('uploadZone').querySelector('.upload-inner').classList.remove('hidden');
  document.getElementById('uploadBtn').disabled = true;
  document.getElementById('analyzeBtn').disabled = true;
  document.getElementById('parseResult').classList.add('hidden');
  state.analysisId = null;
  setProgress(0);
  document.getElementById('uploadProgress').classList.add('hidden');
}

async function uploadResume() {
  const btn  = document.getElementById('uploadBtn');
  const file = btn._file;
  if (!file) return;
  const progressWrap = document.getElementById('uploadProgress');
  progressWrap.classList.remove('hidden');
  let p = 0;
  const pi = setInterval(() => { p = Math.min(p + 8, 88); setProgress(p); }, 120);
  btn.disabled = true;
  btn.innerHTML = `<div class="spinner"></div><span>Parsing…</span>`;
  try {
    const data = await api.resume.upload(file);
    clearInterval(pi); setProgress(100);
    state.analysisId = data.analysis_id;
    const pr = document.getElementById('parseResult');
    pr.classList.remove('hidden');
    document.getElementById('parseResultText').textContent = `✓ ${data.skill_count} skills detected — ready to analyse`;
    document.getElementById('analyzeBtn').disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg><span>Parsed</span>`;
    btn.style.background = 'linear-gradient(135deg,#10b981,#06b6d4)';
    Toast.success(`Resume parsed — ${data.skill_count} skills found!`);
  } catch (err) {
    clearInterval(pi); setProgress(0);
    progressWrap.classList.add('hidden');
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg><span>Upload & Parse</span>`;
    Toast.error(`Upload failed: ${err.message}`);
  }
}

function setProgress(pct) {
  const bar = document.getElementById('progressBar');
  const lbl = document.getElementById('progressLabel');
  if (bar) bar.style.width = pct + '%';
  if (lbl) lbl.textContent = pct < 100 ? `Uploading ${pct}%` : 'Complete';
}

// ── JD Counter ────────────────────────────────────────────────────────────────
function setupJDCounter() {
  const ta = document.getElementById('jobDescription');
  const c  = document.getElementById('jdCount');

  if (!ta) return;
  ta?.addEventListener('input', () => { if (c) c.textContent = `${ta.value.length} chars`; });
}

// ── Tabs ─────────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.dash-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const t = tab.dataset.tab;
      document.querySelectorAll('.dash-tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`tab-${t}`)?.classList.add('active');
    });
  });
}

// ── Profile Tabs ─────────────────────────────────────────────────────────────
function setupProfileTabs() {
  // Find all the profile tabs in the sidebar
  document.querySelectorAll('.prof-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      // Get the name of the tab clicked (e.g., 'security', 'activity')
      const target = tab.dataset.tab; 
      
      // 1. Remove 'active' from all profile tabs and panels
      document.querySelectorAll('.prof-tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.prof-panel').forEach(p => p.classList.remove('active'));
      
      // 2. Add 'active' to the clicked tab
      tab.classList.add('active');
      
      // 3. Add 'active' to the matching panel (e.g., id="panel-security")
      document.getElementById(`panel-${target}`)?.classList.add('active');
    });
  });
}

// ── Analysis ─────────────────────────────────────────────────────────────────
async function runAnalysis() {
  const jd = document.getElementById('jobDescription').value.trim();
  if (!state.analysisId) { Toast.error('Please upload and parse your resume first'); return; }
  if (jd.length < 40)   { Toast.error('Please paste a more complete job description'); return; }
  showLoading('Running AI analysis…');
  try {
    const data = await api.analysis.full(state.analysisId, jd);
    state.lastResult = data;
    renderResults(data);
    Toast.success('Analysis complete!');
    if (Auth.isLoggedIn()) setTimeout(loadHistory, 1000);
  } catch (err) {
    Toast.error(`Analysis failed: ${err.message}`);
  } finally {
    hideLoading();
  }
}

async function runDemo() {
  showLoading('Loading demo analysis…');
  const demoResume = `John Doe | john@email.com | linkedin.com/in/johndoe
  Experience: Backend Developer at TechCorp 2021-Present
  Built REST APIs using Python and Flask. Managed PostgreSQL databases. SQL. Docker deployments on AWS.
  Education: B.E. Computer Engineering 2021
  Skills: Python, JavaScript, HTML, CSS, SQL, PostgreSQL, Docker, Git, Flask, React, Linux, Pandas, NumPy`;
  const demoJD = `Machine Learning Engineer needed.
  Requirements: Python, TensorFlow, PyTorch, scikit-learn, deep learning, NLP, statistics,
  data visualization, SQL, AWS, Docker, Kubernetes, Git, pandas, numpy`;
  document.getElementById('jobDescription').value = demoJD;
  try {
    const data = await api.analysis.quick(demoResume, demoJD);
    state.lastResult = data;
    renderResults(data);
    Toast.info('Demo loaded — sample analysis');
    if (Auth.isLoggedIn()) setTimeout(loadHistory, 1000);
  } catch (err) {
    Toast.error(`Demo failed: ${err.message}`);
  } finally {
    hideLoading();
  }
}

// ── Render pipeline ───────────────────────────────────────────────────────────
function renderResults(d) {
  const section = document.getElementById('resultsSection');
  section.classList.remove('hidden');
  document.getElementById('welcomeState')?.classList.add('hidden');
  setTimeout(() => section.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100);
  renderATSBanner(d);
  renderStatsGrid(d);
  renderCharts(d);
  renderSkillTags('matchedSkills', d.matched_skills, 'matched');
  renderSkillTags('missingSkills', d.missing_skills, 'missing');
  renderJobRecs(d.job_recommendations);
  renderSuggestions(d.suggestions);
  renderLearning(d.learning_resources);
  document.querySelector('[data-tab="skills"]')?.click();
}

function renderATSBanner(d) {
  const score = d.match_score;
  const cls   = score >= 80 ? 'excellent' : score >= 60 ? 'good' : score >= 40 ? 'fair' : 'poor';
  document.getElementById('atsBanner').className = `ats-banner ${cls}`;
  document.getElementById('atsScoreText').textContent = `${score}%`;
  document.getElementById('atsScoreText').className   = `ats-score-text ${cls}`;
  document.getElementById('atsVerdict').textContent   = d.ats_label || cls;
  document.getElementById('atsContext').textContent   =
    `Matches ${d.skill_match_chart.matched} of ${d.skill_match_chart.total_job_skills} required skills`;
  animateGauge(score, cls);
}

function animateGauge(score, cls) {
  const fill = document.getElementById('gaugeFill');
  const pct  = document.getElementById('gaugePct');
  if (!fill) return;
  const circ = 2 * Math.PI * 44;
  const cols = { excellent:'#10b981', good:'url(#gaugeGrad)', fair:'#f59e0b', poor:'#f43f5e' };
  fill.style.stroke = cols[cls] || '#6366f1';
  fill.style.strokeDasharray  = circ;
  fill.style.strokeDashoffset = circ;
  let cur = 0;
  const step = score / 60;
  const timer = setInterval(() => {
    cur = Math.min(cur + step, score);
    fill.style.strokeDashoffset = circ - (cur / 100) * circ;
    if (pct) pct.textContent = Math.round(cur) + '%';
    if (cur >= score) clearInterval(timer);
  }, 16);
}

function renderStatsGrid(d) {
  document.getElementById('statMatched').textContent = d.skill_match_chart.matched;
  document.getElementById('statMissing').textContent = d.skill_match_chart.missing;
  document.getElementById('statResume').textContent  = d.skill_match_chart.total_resume_skills;
  document.getElementById('statJob').textContent     = d.skill_match_chart.total_job_skills;
}

function renderCharts(d) {
  const dc = document.getElementById('doughnutChart')?.getContext('2d');
  if (dc) {
    if (state.charts.doughnut) state.charts.doughnut.destroy();
    state.charts.doughnut = new Chart(dc, {
      type: 'doughnut',
      data: { labels: ['Matched','Missing','Bonus'], datasets: [{ data:[d.skill_match_chart.matched,d.skill_match_chart.missing,d.skill_match_chart.extra], backgroundColor:['#10b981','#f43f5e','#6366f1'], borderWidth:2, borderColor:'#111827', hoverOffset:6 }] },
      options: { responsive:true, maintainAspectRatio:true, cutout:'65%', plugins:{ legend:{ position:'bottom', labels:{ color:'#94a3b8', font:{ size:12 }, padding:16, boxWidth:12 } } }, animation:{ animateRotate:true, duration:900 } }
    });
  }
  const bc = document.getElementById('barChart')?.getContext('2d');
  if (bc) {
    if (state.charts.bar) state.charts.bar.destroy();
    const cats = d.resume_skill_categories || {};
    const labels = Object.keys(cats).map(k => k.replace('_',' ').replace(/\b\w/g,c=>c.toUpperCase()));
    const values = Object.values(cats).map(v=>v.length);
    state.charts.bar = new Chart(bc, {
      type:'bar', data:{ labels, datasets:[{ label:'Skills', data:values, backgroundColor:['#6366f1','#06b6d4','#10b981','#f59e0b','#f43f5e','#8b5cf6','#14b8a6','#f97316'].slice(0,labels.length), borderRadius:6, borderWidth:0 }] },
      options:{ responsive:true, maintainAspectRatio:true, indexAxis:'y', plugins:{ legend:{ display:false } }, scales:{ x:{ grid:{ color:'rgba(255,255,255,0.04)' }, ticks:{ color:'#475569', font:{ size:11 } } }, y:{ grid:{ display:false }, ticks:{ color:'#94a3b8', font:{ size:11 } } } }, animation:{ duration:800 } }
    });
  }
}

function renderSkillTags(id, skills, type) {
  const el = document.getElementById(id);
  if (!el) return;
  el.innerHTML = '';
  if (!skills?.length) { el.innerHTML = `<p class="empty-skills">${type==='missing'?'🎉 No skill gaps!':'No matched skills.'}</p>`; return; }
  skills.forEach((s,i) => {
    const t = document.createElement('span');
    t.className = `skill-tag ${type}`;
    t.textContent = s;
    t.style.animationDelay = `${i*25}ms`;
    el.appendChild(t);
  });
}

function renderJobRecs(jobs) {
  const el = document.getElementById('jobRecs');
  if (!el) return;
  el.innerHTML = '';
  if (!jobs?.length) { el.innerHTML='<p class="empty-skills">No recommendations.</p>'; return; }
  jobs.forEach((job,i) => {
    const c = document.createElement('div');
    c.className = 'job-rec-card';
    c.style.animationDelay = `${i*70}ms`;
    const chips = (job.matching_skills||[]).slice(0,4).map(s=>`<span class="job-chip">${s}</span>`).join('');
    c.innerHTML = `<div class="job-rec-rank">${String(i+1).padStart(2,'0')}</div><div class="job-rec-body"><div class="job-rec-title">${job.title}</div><div class="job-rec-cat">${job.category}</div><div class="job-chips">${chips||'<span class="job-chip">—</span>'}</div></div><div class="job-rec-score-wrap"><div class="job-rec-pct">${job.similarity_score}%</div><div class="job-rec-pct-lbl">match</div></div>`;
    el.appendChild(c);
  });
}

function renderSuggestions(suggestions) {
  const el = document.getElementById('suggestionsList');
  if (!el) return;
  el.innerHTML = '';
  if (!suggestions?.length) { el.innerHTML='<p class="empty-skills">No suggestions.</p>'; return; }
  suggestions.forEach((s,i) => {
    const d = document.createElement('div');
    d.className = 'suggestion-item';
    d.style.animationDelay = `${i*50}ms`;
    d.textContent = s;
    el.appendChild(d);
  });
}

function renderLearning(resources) {
  const el = document.getElementById('learningResources');
  if (!el) return;
  el.innerHTML = '';
  if (!resources||!Object.keys(resources).length) { el.innerHTML='<p class="empty-skills">No learning resources.</p>'; return; }
  Object.entries(resources).forEach(([skill,courses]) => {
    const g = document.createElement('div');
    g.className = 'resource-group';
    g.innerHTML = `<div class="resource-skill-title">${skill}</div>`;
    const l = document.createElement('div');
    l.className = 'resource-cards';
    courses.forEach(c => {
      const p = c.platform.toLowerCase();
      const cls = ['coursera','udemy','youtube'].includes(p) ? p : 'other';
      const a = document.createElement('a');
      a.className = 'resource-card'; a.href=c.url; a.target='_blank'; a.rel='noopener';
      a.innerHTML = `<span class="resource-badge ${cls}">${c.platform}</span><span class="resource-name">${c.course}</span><span class="resource-arrow">↗</span>`;
      l.appendChild(a);
    });
    g.appendChild(l); el.appendChild(g);
  });
}

// ── History ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  const tbody = document.getElementById('historyBody');
  const empty = document.getElementById('historyEmpty');
  if (!tbody) return;
  try {
    // FIX 1: Point to the correct analysis history route
    const records = await api.analysis.history(); 
    
    if (!records.length) { empty?.classList.remove('hidden'); tbody.innerHTML=''; return; }
    empty?.classList.add('hidden');
    
    tbody.innerHTML = records.map(r => {
      const date  = r.created_at ? new Date(r.created_at).toLocaleDateString() : '—';
      
      // FIX 2: Map to 'match_score' instead of 'ats_score'
      const score = r.match_score ?? 0; 
      const cls   = score>=70?'score-high':score>=40?'score-mid':'score-low';
      
      const roles = (r.recommended_roles||[]).slice(0,2).join(', ')||'—';
      const miss  = (r.missing_skills||[]).slice(0,3).join(', ')||'—';
      
      // FIX 3: Map to 'filename' instead of 'resume_name'
      const displayName = r.filename || 'Unknown Resume';
      
      return `<tr>
        <td style="color:var(--text-primary);font-weight:500">${displayName}</td>
        <td><span class="history-score-pill ${cls}">${score.toFixed(0)}%</span></td>
        <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${roles}</td>
        <td style="color:var(--rose);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${miss}</td>
        <td>${date}</td>
      </tr>`;
    }).join('');
  } catch (error) { 
    console.error("Failed to load history:", error);
  }
}

// ── Export / Reset ────────────────────────────────────────────────────────────
function exportResults() {
  const d = state.lastResult;
  if (!d) { Toast.info('No analysis to export yet.'); return; }
  const text = `SkillLens Analysis Report\n${'='.repeat(26)}\nATS Score: ${d.match_score}% — ${d.ats_label}\n\nMatched Skills (${d.matched_skills.length}):\n${d.matched_skills.join(', ')}\n\nMissing Skills (${d.missing_skills.length}):\n${d.missing_skills.join(', ')}\n\nJob Recommendations:\n${(d.job_recommendations||[]).map((j,i)=>`${i+1}. ${j.title} — ${j.similarity_score}%`).join('\n')}\n\nSuggestions:\n${(d.suggestions||[]).join('\n')}\n\nGenerated: ${new Date().toLocaleString()} by SkillLens`;
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text],{type:'text/plain'}));
  a.download = 'skilllens-report.txt';
  a.click();
  Toast.success('Report downloaded!');
}

function resetAll() {
  resetFile();
  document.getElementById('jobDescription').value = '';
  document.getElementById('resultsSection').classList.add('hidden');
  document.getElementById('welcomeState')?.classList.remove('hidden');
  Object.values(state.charts).forEach(c=>c?.destroy());
  state.charts = {}; state.lastResult = null; state.analysisId = null;
  window.scrollTo({top:0,behavior:'smooth'});
}

function showLoading(msg='Analysing…') {
  const el=document.getElementById('loadingOverlay'); const lbl=document.getElementById('loadingLabel');
  if(el) el.classList.remove('hidden'); if(lbl) lbl.textContent=msg;
}
function hideLoading() { document.getElementById('loadingOverlay')?.classList.add('hidden'); }
function fmtSize(b) {
  if(b<1024) return b+' B';
  if(b<1024*1024) return (b/1024).toFixed(1)+' KB';
  return (b/(1024*1024)).toFixed(1)+' MB';
}

// ⬇️ ====== PASTE EVERYTHING BELOW THIS LINE ====== ⬇️

// ── Profile Tab Hydration ─────────────────────────────────────────────────────
function hydrateProfile() {
  const user = Auth.user();
  if (!user) return;

  const nameInput = document.getElementById('profileName');
  const emailInput = document.getElementById('profileEmail');
  const memberSince = document.getElementById('memberSinceDisplay');

  if (nameInput) nameInput.value = user.name || '';
  if (emailInput) emailInput.value = user.email || '';
  
  if (memberSince) {
      const dateStr = user.created_at || new Date().toISOString();
      memberSince.textContent = new Date(dateStr).toLocaleDateString('en-US', {
          month: 'long',
          year: 'numeric'
      });
  }
}

// Run this when the page loads, so the inputs are filled immediately
document.addEventListener('DOMContentLoaded', hydrateProfile);