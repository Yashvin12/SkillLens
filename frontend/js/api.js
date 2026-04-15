/**
 * SkillLens API Client — v3
 * ==========================
 * Centralised HTTP client. Auth helpers separated from nav actions.
 * Added: full /user route group for profile, settings, history.
 */

const API_BASE = 'http://127.0.0.1:8000';

const api = {
  _token() { return localStorage.getItem('sl_token'); },

  _headers(isFormData = false) {
    const h = {};
    if (!isFormData) h['Content-Type'] = 'application/json';
    const t = this._token();
    if (t) h['Authorization'] = `Bearer ${t}`;
    return h;
  },

  async _fetch(method, path, body = null, isFormData = false) {
    const opts = { method, headers: this._headers(isFormData) };
    if (body) opts.body = isFormData ? body : JSON.stringify(body);
    const res  = await fetch(`${API_BASE}${path}`, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.detail || data.message || `HTTP ${res.status}`;
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  },

  get:    (path)       => api._fetch('GET',    path),
  post:   (path, body) => api._fetch('POST',   path, body),
  put:    (path, body) => api._fetch('PUT',    path, body),
  delete: (path)       => api._fetch('DELETE', path),
  upload: (path, fd)   => api._fetch('POST',   path, fd, true),

  // ── Auth (login / register) ───────────────────────────────────────────
  auth: {
    register: (body) => api.post('/auth/register', body),
    login:    (body) => api.post('/auth/login',    body),
    profile:  ()     => api.get('/auth/profile'),
    history:  ()     => api.get('/auth/history'),
  },

  // ── User profile & settings (v3) ──────────────────────────────────────
  user: {
    profile:         ()     => api.get('/profile'),
    updateProfile:   (body) => api.put('/update-profile',  body),
    changePassword:  (body) => api.post('/change-password', body),
    getPrefs:        ()     => api.get('/preferences'),
    savePrefs:       (body) => api.put('/preferences', body),
    history:         ()     => api.get('/history'),
    deleteHistory:   ()     => api.delete('/history'),
  },

  // ── Resume ────────────────────────────────────────────────────────────
  resume: {
    upload: (file) => {
      const fd = new FormData();
      fd.append('file', file);
      return api.upload('/api/resume/upload', fd);
    },
    get: (id) => api.get(`/api/resume/${id}`),
  },

  // ── Analysis ──────────────────────────────────────────────────────────
  analysis: {
    full:    (id, jd)  => api.post('/api/analysis/full',  { analysis_id: id, job_description: jd }),
    quick:   (rt, jd)  => api.post('/api/analysis/quick', { resume_text: rt, job_description: jd }),
    history: ()        => api.get('/api/analysis/history'),
  },
};

// ── Auth helpers (token storage only — navigation is the page's responsibility) ──
const Auth = {
  save(data) {
    localStorage.setItem('sl_token', data.access_token);
    localStorage.setItem('sl_user', JSON.stringify({
      id:    data.user_id,
      name:  data.user_name,
      email: data.user_email,
    }));
  },

  /** Clear token & user cache WITHOUT redirecting — caller decides where to go. */
  clear() {
    localStorage.removeItem('sl_token');
    localStorage.removeItem('sl_user');
  },

  isLoggedIn() { return !!localStorage.getItem('sl_token'); },

  user() {
    try { return JSON.parse(localStorage.getItem('sl_user')); }
    catch { return null; }
  },

  /** Redirect to login if not authenticated; returns false if redirect happened. */
  requireAuth(redirect = 'login.html') {
    if (!this.isLoggedIn()) { window.location.href = redirect; return false; }
    return true;
  },

  /** Redirect to dashboard if already authenticated. */
  redirectIfLoggedIn(redirect = 'dashboard.html') {
    if (this.isLoggedIn()) { window.location.href = redirect; return true; }
    return false;
  },

  /** ✅ CORRECT logout — clears token then sends to login page. */
  logout(loginPage = 'login.html') {
    this.clear();
    window.location.href = loginPage;
  },
};