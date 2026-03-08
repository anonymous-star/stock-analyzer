// === Auth Module ===

const Auth = {
  _user: null,
  KAKAO_APP_KEY: '', // Kakao JavaScript 앱 키 (설정 필요)

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

  async login(username, password) {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    this.setAuth(data.token, data.user);
    return data.user;
  },

  async register(username, password, displayName) {
    const res = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    } catch {
      return false;
    }
  },

  // 카카오 로그인
  async kakaoLogin() {
    if (!this.initKakao()) {
      throw new Error('카카오 앱 키가 설정되지 않았습니다. .env에 KAKAO_JS_KEY를 설정하세요.');
    }

    return new Promise((resolve, reject) => {
      Kakao.Auth.login({
        success: async (authObj) => {
          try {
            // 카카오 유저 정보 요청
            const userInfo = await this._getKakaoUser();
            // 백엔드에 카카오 유저 정보 전달
            const res = await fetch('/auth/kakao', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                kakao_id: String(userInfo.id),
                nickname: userInfo.nickname,
                profile_image: userInfo.profile_image || '',
              }),
            });
            const data = await res.json();
            if (data.error) throw new Error(data.error);
            this.setAuth(data.token, data.user);
            resolve(data.user);
          } catch (err) {
            reject(err);
          }
        },
        fail: (err) => {
          reject(new Error('카카오 로그인 실패'));
        },
      });
    });
  },

  _getKakaoUser() {
    return new Promise((resolve, reject) => {
      Kakao.API.request({
        url: '/v2/user/me',
        success: (res) => {
          const profile = res.kakao_account?.profile || {};
          resolve({
            id: res.id,
            nickname: profile.nickname || '',
            profile_image: profile.thumbnail_image_url || '',
          });
        },
        fail: (err) => reject(new Error('카카오 유저 정보 조회 실패')),
      });
    });
  },

  async verify() {
    const token = this.getToken();
    if (!token) return false;
    try {
      const res = await fetch('/auth/me', {
        headers: { 'Authorization': 'Bearer ' + token },
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
