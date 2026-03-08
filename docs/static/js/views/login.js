// === Login / Register View ===

const LoginView = {
  render(container) {
    const kakaoAvailable = !!Auth.KAKAO_APP_KEY;

    container.innerHTML = `
      <div class="auth-page">
        <div class="auth-card">
          <div class="auth-logo">
            <span class="logo-icon" style="font-size:2rem;width:56px;height:56px;line-height:56px">S</span>
            <h1 class="auth-title">StockPulse</h1>
            <p class="auth-subtitle">AI Stock Analyzer</p>
          </div>

          ${kakaoAvailable ? `
          <button id="kakao-login-btn" class="kakao-login-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="#000"><path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.7 1.8 5.07 4.5 6.39-.15.54-.96 3.48-1.0 3.63 0 0-.02.17.09.24.11.06.24.01.24.01.32-.05 3.72-2.46 4.3-2.88.6.09 1.22.13 1.87.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z"/></svg>
            카카오 로그인
          </button>
          <div class="auth-divider"><span>또는</span></div>
          ` : ''}

          <div class="auth-tabs">
            <button class="auth-tab active" data-tab="login">Login</button>
            <button class="auth-tab" data-tab="register">Sign Up</button>
          </div>

          <!-- Login Form -->
          <form id="login-form" class="auth-form">
            <div class="auth-field">
              <label for="login-username">Username</label>
              <input type="text" id="login-username" placeholder="Enter username" autocomplete="username" required>
            </div>
            <div class="auth-field">
              <label for="login-password">Password</label>
              <input type="password" id="login-password" placeholder="Enter password" autocomplete="current-password" required>
            </div>
            <div id="login-error" class="auth-error hidden"></div>
            <button type="submit" class="auth-submit-btn">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
              Login
            </button>
          </form>

          <!-- Register Form -->
          <form id="register-form" class="auth-form hidden">
            <div class="auth-field">
              <label for="reg-username">Username</label>
              <input type="text" id="reg-username" placeholder="3+ characters" autocomplete="username" required minlength="3">
            </div>
            <div class="auth-field">
              <label for="reg-display">Display Name</label>
              <input type="text" id="reg-display" placeholder="Optional" autocomplete="name">
            </div>
            <div class="auth-field">
              <label for="reg-password">Password</label>
              <input type="password" id="reg-password" placeholder="4+ characters" autocomplete="new-password" required minlength="4">
            </div>
            <div class="auth-field">
              <label for="reg-password2">Confirm Password</label>
              <input type="password" id="reg-password2" placeholder="Re-enter password" autocomplete="new-password" required>
            </div>
            <div id="register-error" class="auth-error hidden"></div>
            <button type="submit" class="auth-submit-btn auth-submit-btn--register">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg>
              Create Account
            </button>
          </form>

          <div class="auth-footer">
            <button class="auth-guest-btn" id="auth-guest-btn">Continue as Guest</button>
          </div>
        </div>
      </div>`;

    this._setupTabs(container);
    this._setupLoginForm(container);
    this._setupRegisterForm(container);

    if (kakaoAvailable) {
      document.getElementById('kakao-login-btn').onclick = () => this._handleKakaoLogin();
    }

    document.getElementById('auth-guest-btn').onclick = () => {
      location.hash = '#/';
    };
  },

  async _handleKakaoLogin() {
    const btn = document.getElementById('kakao-login-btn');
    btn.disabled = true;
    btn.textContent = '로그인 중...';
    try {
      await Auth.kakaoLogin();
      clearApiCache();
      location.hash = '#/';
    } catch (err) {
      const errEl = document.getElementById('login-error');
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    }
    btn.disabled = false;
    btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="#000"><path d="M12 3C6.48 3 2 6.36 2 10.5c0 2.7 1.8 5.07 4.5 6.39-.15.54-.96 3.48-1.0 3.63 0 0-.02.17.09.24.11.06.24.01.24.01.32-.05 3.72-2.46 4.3-2.88.6.09 1.22.13 1.87.13 5.52 0 10-3.36 10-7.5S17.52 3 12 3z"/></svg> 카카오 로그인';
  },

  _setupTabs(container) {
    const tabs = container.querySelectorAll('.auth-tab');
    tabs.forEach(tab => {
      tab.onclick = () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const isLogin = tab.dataset.tab === 'login';
        document.getElementById('login-form').classList.toggle('hidden', !isLogin);
        document.getElementById('register-form').classList.toggle('hidden', isLogin);
      };
    });
  },

  _setupLoginForm(container) {
    const form = document.getElementById('login-form');
    const errEl = document.getElementById('login-error');

    form.onsubmit = async (e) => {
      e.preventDefault();
      errEl.classList.add('hidden');
      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value;
      const btn = form.querySelector('.auth-submit-btn');

      btn.disabled = true;
      btn.textContent = 'Logging in...';

      try {
        await Auth.login(username, password);
        clearApiCache();
        location.hash = '#/';
      } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.remove('hidden');
      }

      btn.disabled = false;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg> Login';
    };
  },

  _setupRegisterForm(container) {
    const form = document.getElementById('register-form');
    const errEl = document.getElementById('register-error');

    form.onsubmit = async (e) => {
      e.preventDefault();
      errEl.classList.add('hidden');
      const username = document.getElementById('reg-username').value.trim();
      const display = document.getElementById('reg-display').value.trim();
      const password = document.getElementById('reg-password').value;
      const password2 = document.getElementById('reg-password2').value;

      if (password !== password2) {
        errEl.textContent = 'Passwords do not match';
        errEl.classList.remove('hidden');
        return;
      }

      const btn = form.querySelector('.auth-submit-btn');
      btn.disabled = true;
      btn.textContent = 'Creating account...';

      try {
        await Auth.register(username, password, display);
        clearApiCache();
        location.hash = '#/';
      } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.remove('hidden');
      }

      btn.disabled = false;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><line x1="20" y1="8" x2="20" y2="14"/><line x1="23" y1="11" x2="17" y2="11"/></svg> Create Account';
    };
  },
};
