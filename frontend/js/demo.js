/**
 * SkillLens Demo Mode — v4
 * =========================
 * Completely self-contained. Zero API calls. Zero backend dependency.
 * All data is hardcoded mock data that mirrors real API response shapes.
 *
 * Public API:
 *   DemoMode.isActive()          → boolean
 *   DemoMode.activate()          → sets flag, adapts UI, runs analysis
 *   DemoMode.exit()              → clears flag, redirects to login
 *   DemoMode.applyUIRestrictions() → hides/disables auth-only nav items
 *   DemoMode.getMockAnalysis()   → returns full mock result object
 */

const DemoMode = (() => {
  const FLAG_KEY  = 'sl_demo_mode';   // sessionStorage key (clears on tab close)
  const USER_KEY  = 'sl_demo_user';

  // ── Mock data (offline, no backend needed) ──────────────────────────────────
  const MOCK_RESULT = {
    analysis_id:   0,
    filename:      'demo_resume.pdf',
    match_score:   72,
    ats_label:     'Good Match',

    resume_skills: [
      'python','javascript','html','css','sql','postgresql','docker',
      'git','flask','react','linux','pandas','numpy','rest api'
    ],
    job_skills: [
      'python','tensorflow','pytorch','scikit-learn','deep learning','nlp',
      'statistics','data visualization','sql','aws','docker','kubernetes',
      'git','pandas','numpy'
    ],
    matched_skills:  ['python','sql','docker','git','pandas','numpy'],
    missing_skills:  ['tensorflow','pytorch','scikit-learn','deep learning','nlp','statistics','aws','kubernetes','data visualization'],
    extra_skills:    ['javascript','html','css','react','flask','linux','rest api','postgresql'],

    skill_match_chart: {
      matched: 6,
      missing: 9,
      extra:   8,
      total_job_skills:    15,
      total_resume_skills: 14,
    },

    resume_skill_categories: {
      programming_languages: ['python','javascript'],
      web_technologies:      ['html','css','react','flask','rest api'],
      databases:             ['sql','postgresql'],
      cloud_devops:          ['docker','git','linux'],
      data_ml:               ['pandas','numpy'],
    },
    job_skill_categories: {
      programming_languages: ['python'],
      data_ml:               ['tensorflow','pytorch','scikit-learn','deep learning','nlp','statistics','data visualization','pandas','numpy'],
      databases:             ['sql'],
      cloud_devops:          ['aws','docker','kubernetes','git'],
    },

    job_recommendations: [
      { title:'Data Scientist',           category:'Data',     similarity_score:88, matching_skills:['python','sql','pandas','numpy'], missing_skills:['r','machine learning','statistics'] },
      { title:'Backend Developer',        category:'Software', similarity_score:85, matching_skills:['python','sql','docker','git','rest api'], missing_skills:['java','node.js'] },
      { title:'Machine Learning Engineer',category:'AI/ML',    similarity_score:72, matching_skills:['python','docker','git','pandas','numpy'], missing_skills:['tensorflow','pytorch','scikit-learn','deep learning','nlp'] },
      { title:'Full Stack Developer',     category:'Software', similarity_score:68, matching_skills:['python','javascript','react','sql','git','html','css'], missing_skills:['node.js','typescript'] },
      { title:'Data Analyst',             category:'Data',     similarity_score:62, matching_skills:['python','sql','pandas'], missing_skills:['excel','tableau','power bi','statistics'] },
    ],

    suggestions: [
      '🎯 Add these high-priority skills to your Skills section: tensorflow, pytorch, scikit-learn, deep learning, nlp',
      '🔗 Add your LinkedIn profile URL — recruiters actively look for this',
      '📝 Add a 3-4 sentence professional summary at the top of your resume',
      '💼 Include a Projects section with 2-3 relevant technical projects',
      '🏆 List any certifications (Google, AWS, Coursera, etc.) to boost credibility',
      '📊 Quantify your achievements (e.g., "Improved performance by 30%")',
      '🔑 Use keywords from the job description to pass ATS filters',
    ],

    learning_resources: {
      tensorflow: [
        { platform:'Coursera', course:'TensorFlow Developer Professional Certificate', url:'https://www.coursera.org/professional-certificates/tensorflow-in-practice' },
        { platform:'YouTube',  course:'TensorFlow 2.0 Complete Course',                url:'https://www.youtube.com/watch?v=tPYj3fFJGjk' },
      ],
      pytorch: [
        { platform:'Udemy',   course:'PyTorch for Deep Learning',           url:'https://www.udemy.com/course/pytorch-for-deep-learning/' },
        { platform:'YouTube', course:'PyTorch Tutorials — Official',        url:'https://www.youtube.com/playlist?list=PLhhyoLH6IjfxeoooqP9rhU3HJIAVAJ3Vz' },
      ],
      'scikit-learn': [
        { platform:'Coursera', course:'Machine Learning Specialization (Andrew Ng)', url:'https://www.coursera.org/specializations/machine-learning-introduction' },
        { platform:'Udemy',    course:'Machine Learning A-Z',                        url:'https://www.udemy.com/course/machinelearning/' },
      ],
      'deep learning': [
        { platform:'Coursera', course:'Deep Learning Specialization',  url:'https://www.coursera.org/specializations/deep-learning' },
        { platform:'YouTube',  course:'Deep Learning — MIT 6.S191',    url:'https://www.youtube.com/watch?v=QDX-1M5Nj7s' },
      ],
      nlp: [
        { platform:'Coursera', course:'Natural Language Processing Specialization', url:'https://www.coursera.org/specializations/natural-language-processing' },
        { platform:'YouTube',  course:'NLP with Python — Sentdex',                 url:'https://www.youtube.com/watch?v=FLZvOKSCkxY' },
      ],
    },

    job_description_preview: 'Machine Learning Engineer position requiring Python, TensorFlow, PyTorch, scikit-learn, deep learning, NLP, AWS, Docker, Kubernetes.',
  };

  const MOCK_JD = `We are looking for a Machine Learning Engineer to join our growing AI team.

Required Skills:
- Python (expert level)
- TensorFlow and PyTorch for model development
- scikit-learn for classical ML algorithms
- Deep Learning and Neural Networks
- Natural Language Processing (NLP)
- Statistics and Mathematics
- Data Visualization tools
- SQL for data querying
- AWS or GCP cloud platforms
- Docker and Kubernetes for deployment
- Git for version control
- Pandas and NumPy`;

  // ── State ────────────────────────────────────────────────────────────────────
  function isActive() {
    return sessionStorage.getItem(FLAG_KEY) === '1';
  }

  function _setActive() {
    sessionStorage.setItem(FLAG_KEY, '1');
    sessionStorage.setItem(USER_KEY, JSON.stringify({ name: 'Demo User', email: 'demo@skilllens.io' }));
  }

  function _clearActive() {
    sessionStorage.removeItem(FLAG_KEY);
    sessionStorage.removeItem(USER_KEY);
    // Also clear any leftover localStorage demo flags from older code
    localStorage.removeItem('sl_run_demo');
    sessionStorage.removeItem('demo');
  }

  function getUser() {
    try { return JSON.parse(sessionStorage.getItem(USER_KEY)); }
    catch { return { name: 'Demo User', email: 'demo@skilllens.io' }; }
  }

  // ── Activation ───────────────────────────────────────────────────────────────
  /**
   * Called from the landing page or any "Try Demo" button.
   * Sets the flag and redirects to dashboard.
   * Dashboard's DOMContentLoaded will pick it up and call runDemoAnalysis().
   */
  function activate(dashboardUrl = 'pages/dashboard.html') {
    _setActive();
    // Clear any real auth so demo and real sessions never mix
    localStorage.removeItem('sl_token');
    localStorage.removeItem('sl_user');
    window.location.href = dashboardUrl;
  }

  /** Called from within the dashboard when it detects demo mode on load. */
  function activateInDashboard() {
    _setActive();
    localStorage.removeItem('sl_token');
    localStorage.removeItem('sl_user');
  }

  // ── Exit ─────────────────────────────────────────────────────────────────────
  function exit(loginUrl = 'login.html') {
    _clearActive();
    window.location.href = loginUrl;
  }

  // ── UI Restrictions ───────────────────────────────────────────────────────────
  /**
   * Called after DOMContentLoaded in demo mode.
   * - Injects the sticky demo banner
   * - Replaces user pill display with "Demo User"
   * - Hides/disables Profile & Settings nav items
   * - Swaps "Try Demo" button to "Exit Demo"
   * - Disables the real upload flow (shows a tooltip)
   */
  function applyUIRestrictions() {
    // 1. Demo banner
    _injectBanner();

    // 2. User pill shows "Demo User" with a distinct colour
    const avatar = document.getElementById('userAvatar');
    const nameEl = document.getElementById('userName');
    if (avatar) { avatar.textContent = '⚡'; avatar.style.background = 'linear-gradient(135deg,#f59e0b,#ef4444)'; }
    if (nameEl)  nameEl.textContent = 'Demo Mode';

    // 3. Hide Profile & Settings from dropdown — replace with demo-specific items
    const ddProfile  = document.getElementById('dropdownProfile');
    const ddSettings = document.querySelector('.dropdown-item[href="profile.html"]');
    if (ddProfile) {
      ddProfile.textContent = '🔒 Profile (login required)';
      ddProfile.style.opacity = '0.4';
      ddProfile.style.cursor  = 'not-allowed';
      ddProfile.addEventListener('click', e => { e.stopPropagation(); e.preventDefault(); Toast.info('Create an account to access your profile.'); });
    }
    if (ddSettings) {
      ddSettings.style.display = 'none';
    }

    // 4. Replace nav "My Profile" link
    document.querySelectorAll('.dash-nav-link[href="profile.html"]').forEach(el => {
      el.removeAttribute('href');
      el.style.opacity = '0.4';
      el.style.cursor  = 'not-allowed';
      el.title = 'Log in to access your profile';
      el.addEventListener('click', e => { e.preventDefault(); Toast.info('Create an account to access your profile.'); });
    });

    // 5. Swap History tab to show demo message
    const histBtn = document.querySelector('.dash-nav-link[onclick*="history"]');
    if (histBtn) {
      histBtn.title = 'Log in to view saved history';
    }

    // 6. Swap "Try Demo" → "Exit Demo"
    const demoBtn = document.getElementById('demoBtn');
    if (demoBtn) {
      demoBtn.textContent = '✕ Exit Demo';
      demoBtn.style.background = 'rgba(244,63,94,0.12)';
      demoBtn.style.borderColor = 'rgba(244,63,94,0.3)';
      demoBtn.style.color = 'var(--rose)';
      demoBtn.onclick = () => exit('login.html');
    }

    // 7. Upload zone — show demo notice instead of real upload
    _patchUploadZoneForDemo();
  }

  function _injectBanner() {
    if (document.getElementById('demoBanner')) return;
    const banner = document.createElement('div');
    banner.id = 'demoBanner';
    banner.innerHTML = `
      <div style="
        position:sticky; top:64px; z-index:90;
        background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(239,68,68,0.10));
        border-bottom:1px solid rgba(245,158,11,0.3);
        padding:10px 32px;
        display:flex; align-items:center; justify-content:space-between;
        gap:16px; flex-wrap:wrap;
      ">
        <div style="display:flex;align-items:center;gap:10px">
          <span style="font-size:16px">⚡</span>
          <span style="font-size:14px;font-weight:600;color:#fbbf24">
            Demo Mode — You're viewing sample data. Some features are limited.
          </span>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap">
          <a href="../pages/signup.html" style="
            font-size:13px;font-weight:700;padding:6px 14px;border-radius:8px;
            background:linear-gradient(135deg,#6366f1,#06b6d4);color:#fff;
            text-decoration:none;white-space:nowrap;
          ">Create Free Account →</a>
          <button onclick="DemoMode.exit('login.html')" style="
            font-size:13px;font-weight:600;padding:6px 14px;border-radius:8px;
            background:rgba(244,63,94,0.12);border:1px solid rgba(244,63,94,0.3);
            color:var(--rose);cursor:pointer;white-space:nowrap;
          ">Exit Demo</button>
        </div>
      </div>`;
    // Insert right after the topbar
    const topbar = document.querySelector('.dash-topbar');
    if (topbar?.nextSibling) {
      topbar.parentNode.insertBefore(banner, topbar.nextSibling);
    } else {
      document.body.prepend(banner);
    }
  }

  function _patchUploadZoneForDemo() {
    const zone = document.getElementById('uploadZone');
    const uploadBtn = document.getElementById('uploadBtn');
    if (!zone) return;

    // Replace upload zone content with demo notice
    const inner = zone.querySelector('.upload-inner');
    if (inner) {
      inner.innerHTML = `
        <div style="font-size:32px;margin-bottom:12px">⚡</div>
        <h4 style="margin-bottom:6px">Demo Mode Active</h4>
        <p style="color:var(--text-muted);font-size:13px">Using sample resume data</p>
        <p style="color:var(--text-dim);font-size:12px;margin-top:8px">Log in to upload a real PDF</p>`;
    }

    // Disable file input and upload button interactions
    const input = document.getElementById('resumeFile');
    if (input) input.disabled = true;
    zone.style.cursor = 'default';
    zone.style.opacity = '0.7';
    zone.onclick = (e) => { e.stopPropagation(); e.preventDefault(); Toast.info('Log in to upload your own resume.'); };

    if (uploadBtn) {
      uploadBtn.disabled = true;
      uploadBtn.style.opacity = '0.4';
    }
  }

  // ── Mock analysis data ────────────────────────────────────────────────────────
  function getMockAnalysis() {
    return JSON.parse(JSON.stringify(MOCK_RESULT)); // deep clone
  }

  function getMockJD() {
    return MOCK_JD;
  }

  return {
    isActive,
    activate,
    activateInDashboard,
    exit,
    applyUIRestrictions,
    getMockAnalysis,
    getMockJD,
    getUser,
  };
})();