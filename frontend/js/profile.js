/**
 * SkillLens Profile & Settings Page
 * ===================================
 * Handles all tabs: Profile, Security, Preferences, Activity.
 * Requires auth — redirects to login if no token.
 */

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  Theme.init();

  // Guard: must be logged in
  if (!Auth.isLoggedIn()) {
    window.location.href = 'login.html';
    return;
  }

  setupNavDropdown();
  setupTabs();
  await loadProfile();
  setupProfileForm();
  setupPasswordForm();
  setupPreferencesForm();
  setupHistoryActions();
});

// ── Dropdown (same as dashboard — profile ≠ logout) ──────────────────────────
function setupNavDropdown() {
  const pill     = document.getElementById('userPill');
  const dropdown = document.getElementById('userDropdown');
  const user     = Auth.user();
  const avatar   = document.getElementById('userAvatar');
  const nameEl   = document.getElementById('userName');

  if (user) {
    if (avatar) avatar.textContent = user.name.charAt(0).toUpperCase();
    if (nameEl) nameEl.textContent = user.name;
  }

  pill?.addEventListener('click', e => { e.stopPropagation(); dropdown?.classList.toggle('hidden'); });
  document.addEventListener('click', () => dropdown?.classList.add('hidden'));
  dropdown?.addEventListener('click', e => e.stopPropagation());

  // Profile → stay on page
  document.getElementById('dropdownProfile')?.addEventListener('click', () => {
    dropdown?.classList.add('hidden');
  });
  // Logout → clear + redirect
  document.getElementById('dropdownLogout')?.addEventListener('click', () => {
    Auth.logout('login.html');
  });
}

// ── Tab Navigation ────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.prof-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const t = tab.dataset.tab;
      document.querySelectorAll('.prof-tab').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.prof-panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${t}`)?.classList.add('active');
    });
  });
}

// ── Load Profile Data ─────────────────────────────────────────────────────────
async function loadProfile() {
  try {
    const data = await api.user.profile();
    renderHero(data);
    prefillProfileForm(data);
    renderStats(data);
    renderHistory(data.recent_history || []);
    Theme.sync(data.preferences);
    prefillPreferences(data.preferences);
  } catch (err) {
    Toast.error('Could not load profile: ' + err.message);
  }
}

function renderHero(data) {
  const initials = data.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0,2);
  const el = document.getElementById('heroAvatar');
  if (el) el.textContent = initials;

  setText('heroName',  data.name);
  setText('heroEmail', data.email);

  const since = data.member_since
    ? new Date(data.member_since).toLocaleDateString('en-US',{month:'long',year:'numeric'})
    : '—';
  setText('heroSince', `Member since ${since}`);
  setText('statTotalAnalyses', data.total_analyses ?? 0);
  setText('statBestScore',     data.best_score     ?? 0);
}

function renderStats(data) {
  setText('statTotalAnalyses', data.total_analyses ?? 0);
  setText('statBestScore',     (data.best_score ?? 0) + '%');
}

function prefillProfileForm(data) {
  setVal('profileName',  data.name);
  setVal('profileEmail', data.email);
}

function prefillPreferences(prefs) {
  if (!prefs) return;
  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) themeToggle.checked = prefs.theme === 'light';
  setSelectVal('langSelect',   prefs.language || 'en');
  setSelectVal('layoutSelect', prefs.layout   || 'detailed');
  setChecked('notifyJobs',     prefs.notify_job_recommendations ?? true);
  setChecked('notifyLearn',    prefs.notify_learning_resources  ?? true);
}

// ── Profile Form ──────────────────────────────────────────────────────────────
function setupProfileForm() {
  document.getElementById('profileForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    clearFormErrors('profileForm');
    const name  = document.getElementById('profileName').value.trim();
    const email = document.getElementById('profileEmail').value.trim();
    if (name.length < 2) { showErr('profileNameErr', 'Name must be at least 2 characters'); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { showErr('profileEmailErr', 'Invalid email'); return; }

    const btn = document.getElementById('saveProfileBtn');
    setBtnLoading(btn, true, 'Saving…');
    try {
      const res = await api.user.updateProfile({ name, email });
      // Update local cache so navbar reflects new name immediately
      const u = Auth.user();
      if (u) { u.name = res.user_name; u.email = res.user_email; localStorage.setItem('sl_user', JSON.stringify(u)); }
      document.getElementById('heroName').textContent  = res.user_name;
      document.getElementById('heroEmail').textContent = res.user_email;
      document.getElementById('heroAvatar').textContent =
        res.user_name.split(' ').map(w=>w[0]).join('').toUpperCase().slice(0,2);
      Toast.success('Profile updated successfully!');
    } catch (err) {
      Toast.error(err.message);
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

// ── Password Form ─────────────────────────────────────────────────────────────
function setupPasswordForm() {
  // Live strength bar
  document.getElementById('newPassword')?.addEventListener('input', e => {
    updateStrengthBar(e.target.value);
  });

  // Live confirm match
  document.getElementById('confirmNewPassword')?.addEventListener('input', () => {
    const np = document.getElementById('newPassword').value;
    const cp = document.getElementById('confirmNewPassword').value;
    if (cp && cp !== np) showErr('confirmPwErr', 'Passwords do not match');
    else clearErr('confirmPwErr');
  });

  // Toggle pw visibility
  document.querySelectorAll('[data-pw-toggle]').forEach(btn => {
    btn.addEventListener('click', () => {
      const inputId = btn.dataset.pwToggle;
      const input = document.getElementById(inputId);
      if (!input) return;
      input.type = input.type === 'password' ? 'text' : 'password';
      btn.querySelector('.eye-open')?.classList.toggle('hidden');
      btn.querySelector('.eye-shut')?.classList.toggle('hidden');
    });
  });

  document.getElementById('passwordForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    clearFormErrors('passwordForm');
    const cur  = document.getElementById('currentPassword').value;
    const np   = document.getElementById('newPassword').value;
    const conf = document.getElementById('confirmNewPassword').value;
    if (!cur) { showErr('currentPwErr', 'Enter your current password'); return; }
    if (np.length < 6) { showErr('newPwErr', 'New password must be at least 6 characters'); return; }
    if (np !== conf)   { showErr('confirmPwErr', 'Passwords do not match'); return; }

    const btn = document.getElementById('changePasswordBtn');
    setBtnLoading(btn, true, 'Updating…');
    try {
      await api.user.changePassword({ current_password: cur, new_password: np, confirm_password: conf });
      document.getElementById('passwordForm').reset();
      resetStrengthBar();
      Toast.success('Password changed successfully!');
    } catch (err) {
      Toast.error(err.message);
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

function updateStrengthBar(pw) {
  let s = 0;
  if (pw.length >= 6)  s++;
  if (pw.length >= 10) s++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) s++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) s++;
  const segs  = document.querySelectorAll('.pw-seg');
  const label = document.querySelector('.pw-strength-label');
  const cls   = ['','active-weak','active-fair','active-good','active-strong'];
  const lbls  = ['','Weak','Fair','Good','Strong'];
  segs.forEach((seg,i) => { seg.className = `pw-seg ${i < s ? cls[s] : ''}`; });
  if (label) label.textContent = pw.length ? lbls[s] : '';
}

function resetStrengthBar() {
  document.querySelectorAll('.pw-seg').forEach(s => s.className = 'pw-seg');
  const l = document.querySelector('.pw-strength-label');
  if (l) l.textContent = '';
}

// ── Preferences Form ──────────────────────────────────────────────────────────
function setupPreferencesForm() {
  // Live theme toggle
  document.getElementById('themeToggle')?.addEventListener('change', e => {
    Theme.set(e.target.checked ? 'light' : 'dark');
  });

  document.getElementById('preferencesForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('savePrefsBtn');
    setBtnLoading(btn, true, 'Saving…');
    try {
      const body = {
        theme:                      Theme.get(),
        language:                   document.getElementById('langSelect')?.value   || 'en',
        layout:                     document.getElementById('layoutSelect')?.value || 'detailed',
        notify_job_recommendations: document.getElementById('notifyJobs')?.checked  ?? true,
        notify_learning_resources:  document.getElementById('notifyLearn')?.checked ?? true,
      };
      await api.user.savePrefs(body);
      Toast.success('Preferences saved!');
    } catch (err) {
      Toast.error(err.message);
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

// ── History ───────────────────────────────────────────────────────────────────
function renderHistory(records) {
  const tbody = document.getElementById('historyTableBody');
  const empty = document.getElementById('historyEmpty');
  if (!tbody) return;
  if (!records.length) {
    empty?.classList.remove('hidden');
    tbody.innerHTML = '';
    return;
  }
  empty?.classList.add('hidden');
  tbody.innerHTML = records.map(r => {
    const date  = r.created_at ? new Date(r.created_at).toLocaleDateString() : '—';
    const score = r.ats_score ?? 0;
    const cls   = score >= 70 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';
    const roles = (r.recommended_roles || []).slice(0,2).join(', ') || '—';
    return `
      <tr>
        <td class="hist-name">${r.resume_name}</td>
        <td><span class="history-score-pill ${cls}">${score.toFixed(0)}%</span></td>
        <td class="hist-roles">${roles}</td>
        <td class="hist-date">${date}</td>
        <td><a href="dashboard.html" class="hist-view-btn">View →</a></td>
      </tr>`;
  }).join('');
}

function setupHistoryActions() {
  // Load full history when Activity tab opens
  document.querySelector('[data-tab="activity"]')?.addEventListener('click', loadFullHistory);

  // Clear history button
  document.getElementById('clearHistoryBtn')?.addEventListener('click', async () => {
    if (!confirm('Delete all your analysis history? This cannot be undone.')) return;
    const btn = document.getElementById('clearHistoryBtn');
    setBtnLoading(btn, true, 'Deleting…');
    try {
      await api.user.deleteHistory();
      Toast.success('History cleared!');
      renderHistory([]);
    } catch (err) {
      Toast.error(err.message);
    } finally {
      setBtnLoading(btn, false);
    }
  });
}

async function loadFullHistory() {
  try {
    const records = await api.user.history();
    renderHistory(records);
  } catch (err) {
    Toast.error('Could not load history');
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setText(id, val) { const el=document.getElementById(id); if(el) el.textContent=val; }
function setVal(id, val)  { const el=document.getElementById(id); if(el) el.value=val; }
function setSelectVal(id, val) { const el=document.getElementById(id); if(el) el.value=val; }
function setChecked(id, val)   { const el=document.getElementById(id); if(el) el.checked=val; }
function showErr(id, msg)    { const el=document.getElementById(id); if(el){el.textContent=msg;} const inp=document.getElementById(id.replace(/Err$/,'').replace('Err','')); inp?.classList.add('error'); }
function clearErr(id)        { const el=document.getElementById(id); if(el) el.textContent=''; }
function clearFormErrors(formId) { document.querySelectorAll(`#${formId} .form-error`).forEach(e=>e.textContent=''); document.querySelectorAll(`#${formId} .error`).forEach(e=>e.classList.remove('error')); }

function setBtnLoading(btn, loading, text='') {
  if (!btn) return;
  if (loading) { btn.disabled=true; btn._orig=btn.innerHTML; btn.innerHTML=`<div class="spinner"></div><span>${text}</span>`; }
  else { btn.disabled=false; btn.innerHTML=btn._orig||btn.innerHTML; }
}