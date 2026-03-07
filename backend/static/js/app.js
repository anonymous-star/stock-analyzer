// === App Router & Init ===

const App = {
  init() {
    this._setupRouter();
    this._setupSearch();
    this._setupModal();
    this._route();
  },

  _setupRouter() {
    window.addEventListener('hashchange', () => this._route());
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

    if (hash.startsWith('#/stock/')) {
      const ticker = decodeURIComponent(hash.slice(8));
      StockDetailView.render(app, ticker);
    } else if (hash.startsWith('#/backtest')) {
      BacktestView.render(app);
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
          dropdown.innerHTML = '<div class="search-item"><span class="search-item-name">결과 없음</span></div>';
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

    // Close dropdown on outside click
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
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
