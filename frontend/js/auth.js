/**
 * Auth Page Logic
 * ================
 * Handles login form, signup form, validation, JWT storage.
 * Shared between pages/login.html and pages/signup.html.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Redirect if already logged in
  if (Auth.isLoggedIn()) {
    window.location.href = 'dashboard.html';
    return;
  }

  // Detect which page we're on
  const page = document.body.dataset.page;
  if (page === 'login') initLogin();
  if (page === 'signup') initSignup();
});

// ── LOGIN ─────────────────────────────────────────────────────────────────────
function initLogin() {
  const form      = document.getElementById('loginForm');
  const emailIn   = document.getElementById('email');
  const passIn    = document.getElementById('password');
  const submitBtn = document.getElementById('submitBtn');
  const serverErr = document.getElementById('serverError');
  const pwToggle  = document.getElementById('pwToggle');

  // Password visibility toggle
  pwToggle?.addEventListener('click', () => togglePw(passIn, pwToggle));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    // Basic client validation
    let valid = true;
    if (!emailIn.value.trim()) { showFieldError('emailError', 'Email is required'); valid = false; }
    if (!passIn.value)         { showFieldError('passError', 'Password is required'); valid = false; }
    if (!valid) return;

    setLoading(submitBtn, true, 'Signing in…');
    hideServerError();

    try {
      const data = await api.auth.login({ email: emailIn.value.trim(), password: passIn.value });
      Auth.save(data);
      Toast.success(`Welcome back, ${data.user_name}!`);
      setTimeout(() => window.location.href = 'dashboard.html', 600);
    } catch (err) {
      showServerError(serverErr, err.message);
      setLoading(submitBtn, false);
    }
  });
}

// ── SIGNUP ────────────────────────────────────────────────────────────────────
function initSignup() {
  const form      = document.getElementById('signupForm');
  const nameIn    = document.getElementById('name');
  const emailIn   = document.getElementById('email');
  const passIn    = document.getElementById('password');
  const confirmIn = document.getElementById('confirmPassword');
  const submitBtn = document.getElementById('submitBtn');
  const serverErr = document.getElementById('serverError');

  // Password strength indicator
  passIn?.addEventListener('input', () => updateStrengthBar(passIn.value));

  // Live confirm match check
  confirmIn?.addEventListener('input', () => {
    if (confirmIn.value && confirmIn.value !== passIn.value) {
      showFieldError('confirmError', 'Passwords do not match');
    } else {
      clearFieldError('confirmError');
    }
  });

  // Toggle visibility
  document.getElementById('pwToggle')?.addEventListener('click', () => togglePw(passIn, document.getElementById('pwToggle')));
  document.getElementById('confirmToggle')?.addEventListener('click', () => togglePw(confirmIn, document.getElementById('confirmToggle')));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();

    let valid = true;
    if (nameIn.value.trim().length < 2) { showFieldError('nameError', 'Name must be at least 2 characters'); valid = false; }
    if (!isValidEmail(emailIn.value))    { showFieldError('emailError', 'Please enter a valid email'); valid = false; }
    if (passIn.value.length < 6)         { showFieldError('passError', 'Password must be at least 6 characters'); valid = false; }
    if (confirmIn.value !== passIn.value){ showFieldError('confirmError', 'Passwords do not match'); valid = false; }
    if (!valid) return;

    setLoading(submitBtn, true, 'Creating account…');
    hideServerError();

    try {
      const data = await api.auth.register({
        name: nameIn.value.trim(),
        email: emailIn.value.trim(),
        password: passIn.value,
        confirm_password: confirmIn.value
      });
      Auth.save(data);
      Toast.success(`Account created! Welcome, ${data.user_name}!`);
      setTimeout(() => window.location.href = 'dashboard.html', 700);
    } catch (err) {
      showServerError(serverErr, err.message);
      setLoading(submitBtn, false);
    }
  });
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function togglePw(input, btn) {
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password';
  btn.innerHTML = show
    ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
    : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
}

function updateStrengthBar(pw) {
  const segs = document.querySelectorAll('.pw-seg');
  const label = document.querySelector('.pw-strength-label');
  if (!segs.length) return;

  let strength = 0;
  if (pw.length >= 6) strength++;
  if (pw.length >= 10) strength++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) strength++;
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) strength++;

  const labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
  const cls    = ['', 'active-weak', 'active-fair', 'active-good', 'active-strong'];

  segs.forEach((seg, i) => {
    seg.className = `pw-seg ${i < strength ? cls[strength] : ''}`;
  });
  if (label) label.textContent = pw.length ? labels[strength] : '';
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function showFieldError(id, msg) {
  const el = document.getElementById(id);
  if (el) el.textContent = msg;
  // Mark input as error
  const input = document.getElementById(id.replace('Error', ''));
  if (input) input.classList.add('error');
}

function clearFieldError(id) {
  const el = document.getElementById(id);
  if (el) el.textContent = '';
  const input = document.getElementById(id.replace('Error', ''));
  if (input) input.classList.remove('error');
}

function clearErrors() {
  document.querySelectorAll('.form-error').forEach(el => el.textContent = '');
  document.querySelectorAll('.form-input.error').forEach(el => el.classList.remove('error'));
}

function showServerError(el, msg) {
  if (!el) return;
  el.textContent = msg;
  el.classList.add('show');
}

function hideServerError() {
  document.querySelectorAll('.auth-server-error').forEach(el => el.classList.remove('show'));
}

function setLoading(btn, loading, text = '') {
  if (!btn) return;
  if (loading) {
    btn.disabled = true;
    btn.dataset.origText = btn.innerHTML;
    btn.innerHTML = `<div class="spinner"></div><span>${text}</span>`;
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.origText || btn.innerHTML;
  }
}