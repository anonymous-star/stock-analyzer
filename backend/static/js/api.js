// === API Client ===

const API = {
  BASE: '',

  async _fetch(url, timeoutMs = 600000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(this.BASE + url, { signal: controller.signal });
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
    const res = await fetch(this.BASE + url, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    return res.json();
  },

  // Recommendations
  getRecommendations(limit = 20) {
    return this._fetch(`/recommendations?limit=${limit}`);
  },

  // Search
  searchStocks(q) {
    return this._fetch(`/stocks/search?q=${encodeURIComponent(q)}`);
  },

  // Stock detail
  getQuote(ticker) {
    return this._fetch(`/stocks/${encodeURIComponent(ticker)}/quote`);
  },

  getTechnical(ticker) {
    return this._fetch(`/stocks/${encodeURIComponent(ticker)}/technical`);
  },

  getFinancials(ticker) {
    return this._fetch(`/stocks/${encodeURIComponent(ticker)}/financials`);
  },

  getNews(ticker, limit = 10) {
    return this._fetch(`/stocks/${encodeURIComponent(ticker)}/news?limit=${limit}`);
  },

  getHistory(ticker, period = '6mo', interval = '1d') {
    return this._fetch(`/stocks/${encodeURIComponent(ticker)}/history?period=${period}&interval=${interval}`);
  },

  // AI Analysis
  analyzeStock(ticker) {
    return this._post(`/stocks/${encodeURIComponent(ticker)}/analyze`);
  },

  // Backtest
  getBacktest(holdDays = 20, limit = 10) {
    return this._fetch(`/backtest?hold_days=${holdDays}&limit=${limit}`);
  },
};
