// === App Router & Init ===

const App = {
  async init() {
    this._setupTheme();
    this._setupRouter();
    this._setupSearch();
    this._setupModal();
    this._setupBuyModal();
    this._setupSellModal();
    this._setupUserMenu();
    this._updateAuthUI();
    this._route();
    // 카카오 SDK 초기화 (config.js에서 키 로드)
    if (Auth.KAKAO_APP_KEY) Auth.initKakao();
  },

  _setupTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    this._updateThemeIcon(saved);

    document.getElementById('theme-toggle').addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme') || 'dark';
      const next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      this._updateThemeIcon(next);
    });
  },

  _updateThemeIcon(theme) {
    const dark = document.getElementById('theme-icon-dark');
    const light = document.getElementById('theme-icon-light');
    if (theme === 'dark') {
      dark.style.display = '';
      light.style.display = 'none';
    } else {
      dark.style.display = 'none';
      light.style.display = '';
    }
  },

  _setupRouter() {
    window.addEventListener('hashchange', () => {
      this._updateAuthUI();
      this._route();
    });
  },

  _route() {
    const hash = location.hash || '#/';
    const app = document.getElementById('app');

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
      const route = link.dataset.route;
      link.classList.toggle('active', hash === '#' + route || (route === '/' && (hash === '' || hash === '#' || hash === '#/')));
    });

    // Reset tab cache on navigation
    StockDetailView._tabLoaded = {};

    if (hash.startsWith('#/login')) {
      LoginView.render(app);
      return;
    } else if (hash.startsWith('#/stock/')) {
      const ticker = decodeURIComponent(hash.slice(8));
      StockDetailView.render(app, ticker);
    } else if (hash.startsWith('#/backtest')) {
      BacktestView.render(app);
    } else if (hash.startsWith('#/strategy')) {
      StrategyView.render(app);
    } else if (hash.startsWith('#/portfolio')) {
      PortfolioView.render(app);
    } else {
      DashboardView.render(app);
    }
  },

  _setupSearch() {
    const input = document.getElementById('search-input');
    const dropdown = document.getElementById('search-dropdown');

    const search = Utils.debounce(async (q) => {
      if (!q || q.length < 1) {
        dropdown.classList.add('hidden');
        return;
      }
      try {
        const res = await API.searchStocks(q);
        const results = res.results || [];
        if (results.length === 0) {
          dropdown.innerHTML = '<div class="search-item"><span class="search-item-name">No results</span></div>';
        } else {
          dropdown.innerHTML = results.map(r =>
            `<div class="search-item" data-ticker="${r.ticker}">
              <span class="search-item-name">${r.name || r.ticker}</span>
              <span class="search-item-ticker">${r.ticker}</span>
            </div>`
          ).join('');

          dropdown.querySelectorAll('.search-item[data-ticker]').forEach(el => {
            el.onclick = () => {
              location.hash = `#/stock/${el.dataset.ticker}`;
              dropdown.classList.add('hidden');
              input.value = '';
            };
          });
        }
        dropdown.classList.remove('hidden');
      } catch {
        dropdown.classList.add('hidden');
      }
    }, 500);

    input.addEventListener('input', e => search(e.target.value.trim()));
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const val = input.value.trim();
        if (val) {
          location.hash = `#/stock/${val.toUpperCase()}`;
          dropdown.classList.add('hidden');
          input.value = '';
        }
      }
    });

    document.addEventListener('click', e => {
      if (!e.target.closest('.search-box')) {
        dropdown.classList.add('hidden');
      }
    });
  },

  _setupModal() {
    const modal = document.getElementById('ai-modal');
    modal.querySelector('.modal-close').onclick = () => modal.classList.add('hidden');
    modal.querySelector('.modal-overlay').onclick = () => modal.classList.add('hidden');
  },

  _setupBuyModal() {
    const modal = document.getElementById('buy-modal');
    const btn = document.getElementById('buy-confirm-btn');
    btn.addEventListener('click', async () => {
      const ticker = document.getElementById('buy-ticker').value;
      const name = document.getElementById('buy-name').value;
      const qty = parseInt(document.getElementById('buy-qty').value) || 1;
      const tp = parseFloat(document.getElementById('buy-tp').value) || 5;
      const sl = parseFloat(document.getElementById('buy-sl').value) || -5;
      const hold = parseInt(document.getElementById('buy-hold').value) || 20;

      btn.disabled = true;
      btn.textContent = 'Processing...';

      try {
        const res = await fetch(API.BASE + '/portfolio/buy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1', ...API._authHeaders() },
          body: JSON.stringify({
            ticker, name, quantity: qty,
            tp_pct: tp, sl_pct: sl, hold_days: hold,
          }),
        });
        const data = await res.json();
        if (data.error) {
          App.toast(data.error, 'error');
        } else {
          App.toast(`${ticker} ${qty}x bought @ ${Utils.formatPrice(data.buy_price, document.getElementById('buy-currency').value)}`, 'success');
          API.invalidatePortfolio();
          modal.classList.add('hidden');
          PortfolioView.refreshData();
        }
      } catch (err) {
        App.toast('Buy failed: ' + err.message, 'error');
      }
      btn.disabled = false;
      btn.textContent = 'Buy Now';
    });
  },

  // Open buy modal for a stock
  openBuyModal(ticker, name, price, currency) {
    const modal = document.getElementById('buy-modal');
    document.getElementById('buy-modal-title').textContent = `Buy ${ticker}`;
    document.getElementById('buy-ticker').value = ticker;
    document.getElementById('buy-name').value = name || ticker;
    document.getElementById('buy-currency').value = currency || 'USD';
    document.getElementById('buy-price-display').textContent = Utils.formatPrice(price, currency);
    const nameEl = document.getElementById('buy-stock-name');
    if (nameEl) nameEl.textContent = name || '';
    document.getElementById('buy-qty').value = 1;
    document.getElementById('buy-tp').value = 5;
    document.getElementById('buy-sl').value = -5;
    document.getElementById('buy-hold').value = 20;
    this._updateBuyTotal(price, currency);

    // Live total update
    const qtyInput = document.getElementById('buy-qty');
    qtyInput.oninput = () => this._updateBuyTotal(price, currency);

    modal.classList.remove('hidden');
  },

  _updateBuyTotal(price, currency) {
    const qty = parseInt(document.getElementById('buy-qty').value) || 1;
    const total = price * qty;
    const el = document.getElementById('buy-total-display');
    if (el) el.textContent = Utils.formatPrice(total, currency);
  },

  // === Sell Modal ===
  _setupSellModal() {
    const modal = document.getElementById('sell-modal');
    const btn = document.getElementById('sell-confirm-btn');
    modal.querySelector('.modal-overlay').onclick = () => modal.classList.add('hidden');

    // "All" button
    document.getElementById('sell-qty-all').addEventListener('click', () => {
      const max = parseInt(document.getElementById('sell-max-qty').value) || 1;
      document.getElementById('sell-qty').value = max;
      document.getElementById('sell-qty').dispatchEvent(new Event('input'));
    });

    btn.addEventListener('click', async () => {
      const ticker = document.getElementById('sell-ticker-val').value;
      const reason = document.getElementById('sell-reason-val').value || 'manual';
      const quantity = parseInt(document.getElementById('sell-qty').value) || 1;

      btn.disabled = true;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6 6 18M6 6l12 12"/></svg> Processing...';

      try {
        const res = await fetch(API.BASE + '/portfolio/sell', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': '1', ...API._authHeaders() },
          body: JSON.stringify({ ticker, quantity, reason }),
        });
        const data = await res.json();
        if (data.error) {
          App.toast(data.error, 'error');
        } else {
          const ret = data.return_pct != null ? data.return_pct.toFixed(2) : '0';
          App.toast(`${ticker} ${data.quantity_sold}x sold (${ret >= 0 ? '+' : ''}${ret}%)`, parseFloat(ret) >= 0 ? 'success' : 'error');
          API.invalidatePortfolio();
          modal.classList.add('hidden');
          PortfolioView.refreshData();
        }
      } catch (err) {
        App.toast('Sell failed: ' + err.message, 'error');
      }

      btn.disabled = false;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6 6 18M6 6l12 12"/></svg> Sell Now';
    });
  },

  openSellModal({ ticker, name, totalQty, curPrice, avgPrice, returnText, returnColor, reason, currency }) {
    const modal = document.getElementById('sell-modal');
    document.getElementById('sell-modal-title').textContent = `Sell ${ticker}`;
    document.getElementById('sell-ticker-val').value = ticker;
    document.getElementById('sell-reason-val').value = reason || 'manual';
    document.getElementById('sell-max-qty').value = totalQty;
    document.getElementById('sell-display-ticker').textContent = ticker;
    document.getElementById('sell-display-name').textContent = name || '';
    document.getElementById('sell-display-buy-price').textContent = avgPrice || '-';
    document.getElementById('sell-display-cur-price').textContent = curPrice || '-';

    const retEl = document.getElementById('sell-display-return');
    retEl.textContent = returnText || '-';
    retEl.style.color = returnColor || '';

    const reasonRow = document.getElementById('sell-reason-row');
    const reasonDisplay = document.getElementById('sell-display-reason');
    if (reason && reason !== 'manual') {
      reasonRow.style.display = '';
      reasonDisplay.textContent = reason;
    } else {
      reasonRow.style.display = 'none';
    }

    // Qty input setup
    const qtyInput = document.getElementById('sell-qty');
    const qtyHint = document.getElementById('sell-qty-hint');
    qtyInput.value = 1;
    qtyInput.max = totalQty;
    qtyHint.textContent = `(max: ${totalQty})`;

    // Parse numeric price for total calculation
    const priceNum = parseFloat(String(curPrice).replace(/[^0-9.\-]/g, '')) || 0;
    const cur = currency || 'USD';

    const updateTotal = () => {
      const q = Math.min(Math.max(parseInt(qtyInput.value) || 1, 1), totalQty);
      const total = priceNum * q;
      document.getElementById('sell-total-display').textContent = Utils.formatPrice(total, cur);
    };
    qtyInput.oninput = updateTotal;
    updateTotal();

    // Icon color based on return
    const icon = document.getElementById('sell-form-icon');
    const isLoss = (returnText || '').includes('-');
    icon.innerHTML = isLoss
      ? '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--sell)" stroke-width="1.5"><path d="M12 9v4m0 4h.01M3 12a9 9 0 1 1 18 0 9 9 0 0 1-18 0z"/></svg>'
      : '<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--buy)" stroke-width="1.5"><path d="M9 12l2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"/></svg>';

    modal.classList.remove('hidden');
  },

  _setupUserMenu() {
    const btn = document.getElementById('user-menu-btn');
    const dropdown = document.getElementById('user-dropdown');
    const logoutBtn = document.getElementById('logout-btn');

    btn.addEventListener('click', () => {
      dropdown.classList.toggle('hidden');
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('.user-menu')) {
        dropdown.classList.add('hidden');
      }
    });

    logoutBtn.addEventListener('click', () => {
      Auth.logout();
      this._updateAuthUI();
    });
  },

  _updateAuthUI() {
    const user = Auth.getUser();
    const userMenu = document.getElementById('user-menu');
    const loginBtn = document.getElementById('login-nav-btn');
    const nameEl = document.getElementById('user-display-name');
    const infoEl = document.getElementById('user-dropdown-info');

    if (user && Auth.isLoggedIn()) {
      userMenu.classList.remove('hidden');
      loginBtn.classList.add('hidden');
      nameEl.textContent = user.display_name || user.username;
      infoEl.textContent = user.username;
      // 카카오 프로필 이미지
      const btn = document.getElementById('user-menu-btn');
      const existingImg = btn.querySelector('.user-avatar');
      if (user.profile_image && !existingImg) {
        const img = document.createElement('img');
        img.className = 'user-avatar';
        img.src = user.profile_image;
        img.alt = '';
        btn.insertBefore(img, btn.firstChild);
        btn.querySelector('svg')?.remove();
      }
    } else {
      userMenu.classList.add('hidden');
      loginBtn.classList.remove('hidden');
    }
  },

  toast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast toast--${type}`;
    el.textContent = msg;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  },
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
