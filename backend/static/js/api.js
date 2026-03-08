// === Client-side Cache ===

const _apiCache = {};

function _cached(key, ttlMs, fetcher) {
  const entry = _apiCache[key];
  if (entry && Date.now() - entry.ts < ttlMs) {
    return Promise.resolve(entry.data);
  }
  // 동일 key 동시 호출 방지 (in-flight dedup)
  if (entry && entry.promise) return entry.promise;
  const promise = fetcher().then(data => {
    _apiCache[key] = { data, ts: Date.now(), promise: null };
    return data;
  }).catch(err => {
    if (_apiCache[key]) _apiCache[key].promise = null;
    throw err;
  });
  _apiCache[key] = { ...(entry || {}), promise };
  return promise;
}

// 캐시 무효화
function clearApiCache(prefix) {
  if (!prefix) {
    Object.keys(_apiCache).forEach(k => delete _apiCache[k]);
  } else {
    Object.keys(_apiCache).filter(k => k.startsWith(prefix)).forEach(k => delete _apiCache[k]);
  }
}

// === TTL 기준 ===
// Dashboard (추천):  5분 — 백엔드 1시간 캐시 위에 빠른 재방문 대응
// Stock quote:       2분 — 실시간성 중요
// Technical:         3분 — 일봉 기반이라 자주 안 바뀜
// Financials:       10분 — 거의 안 바뀜
// News:              5분 — 적당한 신선도
// History:           5분 — 차트 데이터
// Backtest:         10분 — 백엔드 8시간 캐시
// Portfolio:         1분 — 매도 시그널 신선도 중요
// Advisor:           5분 — 백엔드 30분 캐시
// Search:            캐시 안 함

const TTL = {
  REC:       10 * 60 * 1000,  // 10분 (백엔드 1시간 캐시)
  QUOTE:      3 * 60 * 1000,  // 3분
  TECH:       5 * 60 * 1000,  // 5분
  FIN:       15 * 60 * 1000,  // 15분
  NEWS:      10 * 60 * 1000,  // 10분
  HISTORY:   10 * 60 * 1000,  // 10분
  BACKTEST:  15 * 60 * 1000,  // 15분
  PORTFOLIO:  3 * 60 * 1000,  // 3분 (매수/매도 시 수동 무효화)
  ADVISOR:   10 * 60 * 1000,  // 10분
  MODEL:     15 * 60 * 1000,  // 15분
  REGIME:     5 * 60 * 1000,  // 5분 (시장 레짐)
};

// === API Client ===

const API = {
  BASE: '',

  _authHeaders() {
    const token = Auth.getToken();
    const headers = {};
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return headers;
  },

  async _fetch(url, timeoutMs = 600000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(this.BASE + url, {
        signal: controller.signal,
        headers: this._authHeaders(),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return res.json();
    } finally {
      clearTimeout(timer);
    }
  },

  async _post(url) {
    const res = await fetch(this.BASE + url, {
      method: 'POST',
      headers: this._authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Recommendations (5분 캐시)
  getRecommendations(limit = 20) {
    return _cached(`rec:${limit}`, TTL.REC, () => this._fetch(`/recommendations?limit=${limit}`));
  },

  // Search (캐시 안 함)
  searchStocks(q) {
    return this._fetch(`/stocks/search?q=${encodeURIComponent(q)}`);
  },

  // Stock detail (종목별 캐시)
  getQuote(ticker) {
    return _cached(`quote:${ticker}`, TTL.QUOTE, () => this._fetch(`/stocks/${encodeURIComponent(ticker)}/quote`));
  },

  getTechnical(ticker) {
    return _cached(`tech:${ticker}`, TTL.TECH, () => this._fetch(`/stocks/${encodeURIComponent(ticker)}/technical`));
  },

  getFinancials(ticker) {
    return _cached(`fin:${ticker}`, TTL.FIN, () => this._fetch(`/stocks/${encodeURIComponent(ticker)}/financials`));
  },

  getNews(ticker, limit = 10) {
    return _cached(`news:${ticker}:${limit}`, TTL.NEWS, () => this._fetch(`/stocks/${encodeURIComponent(ticker)}/news?limit=${limit}`));
  },

  getHistory(ticker, period = '6mo', interval = '1d') {
    return _cached(`hist:${ticker}:${period}:${interval}`, TTL.HISTORY, () => this._fetch(`/stocks/${encodeURIComponent(ticker)}/history?period=${period}&interval=${interval}`));
  },

  // AI Analysis (캐시 안 함 — 매번 새로 분석)
  analyzeStock(ticker) {
    return this._post(`/stocks/${encodeURIComponent(ticker)}/analyze`);
  },

  // Backtest (10분 캐시)
  getBacktest(holdDays = 20, limit = 10) {
    return _cached(`bt:${holdDays}:${limit}`, TTL.BACKTEST, () => this._fetch(`/backtest?hold_days=${holdDays}&limit=${limit}`));
  },

  // Portfolio (1분 캐시)
  getPortfolio() {
    return _cached('portfolio', TTL.PORTFOLIO, () => this._fetch('/portfolio'));
  },

  getPortfolioHistory(limit = 30) {
    return _cached(`pf-hist:${limit}`, TTL.PORTFOLIO, () => this._fetch(`/portfolio/history?limit=${limit}`));
  },

  // 시장 레짐 (5분 캐시, 가벼움)
  getMarketRegime() {
    return _cached('regime', TTL.REGIME, () => this._fetch('/portfolio/market-regime'));
  },

  // AI Advisor (10분 캐시)
  getAdvisor() {
    return _cached('advisor', TTL.ADVISOR, () => this._fetch('/portfolio/advisor', 120000));
  },

  // Model Info (10분 캐시)
  getModelInfo() {
    return _cached('model-info', TTL.MODEL, () => this._fetch('/model/info'));
  },

  // 캐시 무효화 (매수/매도 후 호출)
  invalidatePortfolio() {
    clearApiCache('portfolio');
    clearApiCache('pf-hist');
    clearApiCache('advisor');
  },
};
