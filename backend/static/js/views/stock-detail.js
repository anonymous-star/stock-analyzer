// === Stock Detail View ===

const StockDetailView = {
  _ticker: null,
  _quoteData: null,

  async render(container, ticker) {
    this._ticker = ticker;
    Utils.showSpinner(container, `${ticker} 데이터 로딩 중...`);

    try {
      const quote = await API.getQuote(ticker);
      this._quoteData = quote;
      container.innerHTML = '';

      // Header
      container.appendChild(this._renderHeader(quote));

      // Tabs
      const tabContainer = document.createElement('div');
      const tabs = ['차트', '기술적', '재무', '뉴스'];
      const tabsNav = document.createElement('div');
      tabsNav.className = 'tabs';

      const panels = document.createElement('div');

      tabs.forEach((label, idx) => {
        const btn = document.createElement('button');
        btn.className = 'tab-btn' + (idx === 0 ? ' active' : '');
        btn.textContent = label;
        btn.onclick = () => this._switchTab(tabsNav, panels, idx);
        tabsNav.appendChild(btn);

        const panel = document.createElement('div');
        panel.className = 'tab-panel' + (idx === 0 ? ' active' : '');
        panel.dataset.tab = idx;
        panels.appendChild(panel);
      });

      tabContainer.appendChild(tabsNav);
      tabContainer.appendChild(panels);
      container.appendChild(tabContainer);

      // Load first tab (chart)
      this._loadTab(panels, 0);
    } catch (err) {
      container.innerHTML = `<div class="empty-state">데이터 로딩 실패: ${err.message}</div>`;
    }
  },

  _renderHeader(quote) {
    const header = document.createElement('div');
    header.className = 'stock-header';
    const changeCls = Utils.changeClass(quote.change_percent);
    const week52 = quote['52_week_high'] && quote['52_week_low']
      ? `<div class="stock-week52">52주 ${Utils.formatPrice(quote['52_week_low'], quote.currency)} ~ ${Utils.formatPrice(quote['52_week_high'], quote.currency)}</div>`
      : '';

    header.innerHTML = `
      <div class="stock-header-top">
        <div>
          <h1>${quote.name || this._ticker}</h1>
          <span class="ticker-label">${this._ticker}</span>
        </div>
        <div class="stock-price-block">
          <div class="price">${Utils.formatPrice(quote.current_price, quote.currency)}</div>
          <div class="change ${changeCls}">${Utils.formatChange(quote.change_percent)}</div>
          ${week52}
        </div>
      </div>
      <button class="ai-analyze-btn" id="ai-btn">AI 종합 분석</button>
    `;

    header.querySelector('#ai-btn').onclick = () => this._runAiAnalysis();
    return header;
  },

  _switchTab(tabsNav, panels, idx) {
    tabsNav.querySelectorAll('.tab-btn').forEach((b, i) => b.classList.toggle('active', i === idx));
    panels.querySelectorAll('.tab-panel').forEach((p, i) => p.classList.toggle('active', i === idx));
    this._loadTab(panels, idx);
  },

  _tabLoaded: {},

  async _loadTab(panels, idx) {
    const key = this._ticker + '_' + idx;
    if (this._tabLoaded[key]) return;
    this._tabLoaded[key] = true;

    const panel = panels.querySelector(`[data-tab="${idx}"]`);

    switch (idx) {
      case 0: // Chart
        Utils.showSpinner(panel, '차트 로딩 중...');
        await PriceChart.render(panel, this._ticker);
        break;
      case 1: // Technical
        Utils.showSpinner(panel, '기술적 지표 로딩 중...');
        try {
          const tech = await API.getTechnical(this._ticker);
          Indicators.render(panel, tech);
        } catch (err) {
          panel.innerHTML = `<div class="empty-state">${err.message}</div>`;
        }
        break;
      case 2: // Financial
        Utils.showSpinner(panel, '재무 데이터 로딩 중...');
        try {
          const fin = await API.getFinancials(this._ticker);
          Financials.render(panel, fin);
        } catch (err) {
          panel.innerHTML = `<div class="empty-state">${err.message}</div>`;
        }
        break;
      case 3: // News
        Utils.showSpinner(panel, '뉴스 로딩 중...');
        try {
          const news = await API.getNews(this._ticker);
          NewsList.render(panel, news);
        } catch (err) {
          panel.innerHTML = `<div class="empty-state">${err.message}</div>`;
        }
        break;
    }
  },

  async _runAiAnalysis() {
    const modal = document.getElementById('ai-modal');
    const body = document.getElementById('ai-modal-body');
    modal.classList.remove('hidden');
    Utils.showSpinner(body, 'AI가 분석 중입니다... (30초~1분 소요)');

    const btn = document.getElementById('ai-btn');
    if (btn) { btn.disabled = true; btn.textContent = '분석 중...'; }

    try {
      const result = await API.analyzeStock(this._ticker);
      this._renderAiResult(body, result);
    } catch (err) {
      body.innerHTML = `<div class="empty-state">AI 분석 실패: ${err.message}</div>`;
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'AI 종합 분석'; }
    }
  },

  _renderAiResult(container, result) {
    const recColor = result.recommendation === 'BUY' ? 'var(--buy)' : result.recommendation === 'SELL' ? 'var(--sell)' : 'var(--hold)';
    const stars = '★'.repeat(result.confidence || 0) + '☆'.repeat(5 - (result.confidence || 0));
    const recLabel = Utils.recLabel(result.recommendation);

    let html = `
      <div style="text-align:center;margin-bottom:1.5rem">
        <span class="ai-rec-badge" style="background:${recColor}22;color:${recColor}">${recLabel}</span>
        <span class="ai-confidence-stars" style="color:${recColor}">${stars}</span>
      </div>
    `;

    if (result.target_price_low || result.target_price_high) {
      html += `<div class="ai-result-section">
        <h3>목표가</h3>
        <p>${result.target_price_low ? Utils.formatNumber(result.target_price_low) : '?'} ~ ${result.target_price_high ? Utils.formatNumber(result.target_price_high) : '?'}</p>
      </div>`;
    }

    if (result.overall_summary) {
      html += `<div class="ai-result-section"><h3>종합 의견</h3><p>${result.overall_summary}</p></div>`;
    }

    if (result.investment_points && result.investment_points.length > 0) {
      html += `<div class="ai-result-section"><h3>투자 포인트</h3><ul>${result.investment_points.map(p => `<li>${p}</li>`).join('')}</ul></div>`;
    }

    if (result.risk_factors && result.risk_factors.length > 0) {
      html += `<div class="ai-result-section"><h3>리스크 요인</h3><ul>${result.risk_factors.map(r => `<li>${r}</li>`).join('')}</ul></div>`;
    }

    if (result.technical_summary) {
      html += `<div class="ai-result-section"><h3>기술적 분석</h3><p>${result.technical_summary}</p></div>`;
    }

    if (result.fundamental_summary) {
      html += `<div class="ai-result-section"><h3>펀더멘털 분석</h3><p>${result.fundamental_summary}</p></div>`;
    }

    container.innerHTML = html;
  },
};
