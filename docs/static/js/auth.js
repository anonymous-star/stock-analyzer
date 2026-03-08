// === Auth Module ===

const Auth = {
  _user: null,
  KAKAO_APP_KEY: window.__KAKAO_KEY || '', // config.js에서 로드

  getToken() {
    return localStorage.getItem('auth_token');
  },

  getUser() {
    if (this._user) return this._user;
    const raw = localStorage.getItem('auth_user');
    if (raw) {
      try { this._user = JSON.parse(raw); } catch { this._user = null; }
    }
    return this._user;
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  setAuth(token, user) {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('auth_user', JSON.stringify(user));
    this._user = user;
  },

  logout() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user');
    this._user = null;
    clearApiCache();
    // 카카오 로그아웃 (SDK 초기화된 경우)
    try {
      if (window.Kakao && Kakao.Auth && Kakao.Auth.getAccessToken()) {
        Kakao.Auth.logout();
      }
    } catch {}
    location.hash = '#/login';
  },

  _base() { return window.__API_BASE || ''; },

  async login(username, password) {
    const res = await fetch(this._base() + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    this.setAuth(data.token, data.user);
    return data.user;
  },

  async register(username, password, displayName) {
    const res = await fetch(this._base() + '/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1' },
      body: JSON.stringify({ username, password, display_name: displayName }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    this.setAuth(data.token, data.user);
    return data.user;
  },

  // 카카오 SDK 초기화
  initKakao() {
    if (!this.KAKAO_APP_KEY) return false;
    try {
      if (window.Kakao && !Kakao.isInitialized()) {
        Kakao.init(this.KAKAO_APP_KEY);
      }
      return window.Kakao && Kakao.isInitialized();
    } catch (e) {
      console.warn('Kakao init error:', e);
      return false;
    }
  },

  // 카카오 SDK 로드 대기 (최대 5초)
  _waitForKakaoSDK() {
    return new Promise((resolve) => {
      if (window.Kakao) return resolve(true);
      let tries = 0;
      const check = setInterval(() => {
        tries++;
        if (window.Kakao) { clearInterval(check); resolve(true); }
        else if (tries > 50) { clearInterval(check); resolve(false); }
      }, 100);
    });
  },

  // 카카오 로그인 (SDK v2 — redirect flow)
  async kakaoLogin() {
    await this._waitForKakaoSDK();
    if (!this.initKakao()) {
      throw new Error('카카오 SDK 로드에 실패했습니다. 페이지를 새로고침 해주세요.');
    }
    // Redirect to Kakao login — page navigates away
    const redirectUri = window.location.origin + window.location.pathname;
    Kakao.Auth.authorize({ redirectUri, scope: 'profile_nickname,profile_image', prompt: 'login' });
  },

  // 카카오 OAuth 콜백 처리 (App.init에서 호출)
  async handleKakaoCallback(code) {
    const redirectUri = window.location.origin + window.location.pathname;
    const res = await fetch(this._base() + '/auth/kakao', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1' },
      body: JSON.stringify({ code, redirect_uri: redirectUri }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    this.setAuth(data.token, data.user);
    return data.user;
  },

  async verify() {
    const token = this.getToken();
    if (!token) return false;
    try {
      const res = await fetch(this._base() + '/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token, 'ngrok-skip-browser-warning': '1' },
      });
      const data = await res.json();
      if (data.error) {
        this.logout();
        return false;
      }
      this._user = data.user;
      localStorage.setItem('auth_user', JSON.stringify(data.user));
      return true;
    } catch {
      return false;
    }
  },
};
