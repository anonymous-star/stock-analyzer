// === Portfolio View ===

const PortfolioView = {
  _cache: null,
  _container: null,

  async render(container) {
    this._cache = null;
    this._container = container;
    Utils.showSpinner(container, 'Loading portfolio...');

    try {
      const [holdingsRes, historyRes] = await Promise.all([
        API.getPortfolio(),
        API.getPortfolioHistory(100),
      ]);

      const grouped = holdingsRes.grouped || [];
      const holdings = holdingsRes.holdings || [];
      const summary = holdingsRes.summary || {};
      const trades = historyRes.trades || [];
      const cumPnl = historyRes.cumulative_pnl || [];

      container.innerHTML = '';
      const frag = document.createElement('div');
      frag.className = 'pf-dashboard';

      // 0. AI Advisor
      const advisorEl = document.createElement('div');
      advisorEl.id = 'advisor-section';
      advisorEl.className = 'pf-section';
      advisorEl.innerHTML = `
        <div class="strat-section-head">
          <h2 class="strat-section-title">AI Coach</h2>
          <button id="btn-load-advisor" class="strat-btn strat-btn--primary" style="font-size:.8rem;padding:.4rem 1rem">
            AI 분석 요청
          </button>
        </div>
        <div id="advisor-body" class="strat-card strat-card--accent" style="min-height:60px;display:flex;align-items:center;justify-content:center;color:var(--text-muted);font-size:.85rem">
          버튼을 눌러 AI 코치의 맞춤 투자 가이드를 받으세요
        </div>
      `;
      frag.appendChild(advisorEl);

      // 1. Summary KPI
      const kpiSection = this._summarySection(summary, holdings, cumPnl);
      kpiSection.id = 'pf-kpi-section';
      frag.appendChild(kpiSection);

      // 2. Grouped holdings
      const holdSection = this._holdingsSection(grouped);
      holdSection.id = 'pf-holdings-section';
      frag.appendChild(holdSection);

      // 3. Full trade history (buy + sell)
      const histSection = this._historySection(trades);
      histSection.id = 'pf-history-section';
      frag.appendChild(histSection);

      container.appendChild(frag);
      this._bindEvents(container);
    } catch (err) {
      container.innerHTML = `<div class="empty-state">Portfolio load failed: ${err.message}</div>`;
    }
  },

  // 부분 갱신: holdings + KPI + history만 교체 (AI advisor 보존)
  async refreshData() {
    const container = this._container || document.getElementById('app');
    // 포트폴리오 뷰가 아니면 무시
    if (!container.querySelector('#pf-holdings-section')) return;

    try {
      const [holdingsRes, historyRes] = await Promise.all([
        API.getPortfolio(),
        API.getPortfolioHistory(100),
      ]);

      const grouped = holdingsRes.grouped || [];
      const holdings = holdingsRes.holdings || [];
      const summary = holdingsRes.summary || {};
      const trades = historyRes.trades || [];
      const cumPnl = historyRes.cumulative_pnl || [];

      // KPI 교체
      const oldKpi = document.getElementById('pf-kpi-section');
      if (oldKpi) {
        const newKpi = this._summarySection(summary, holdings, cumPnl);
        newKpi.id = 'pf-kpi-section';
        oldKpi.replaceWith(newKpi);
      }

      // Holdings 교체
      const oldHold = document.getElementById('pf-holdings-section');
      if (oldHold) {
        const newHold = this._holdingsSection(grouped);
        newHold.id = 'pf-holdings-section';
        oldHold.replaceWith(newHold);
      }

      // History 교체
      const oldHist = document.getElementById('pf-history-section');
      if (oldHist) {
        const newHist = this._historySection(trades);
        newHist.id = 'pf-history-section';
        oldHist.replaceWith(newHist);
      }
    } catch (err) {
      // 부분 갱신 실패 시 조용히 무시
    }
  },

  _bindEvents(container) {
    // Advisor button
    const advBtn = document.getElementById('btn-load-advisor');
    if (advBtn && !advBtn._bound) {
      advBtn._bound = true;
      advBtn.addEventListener('click', async () => {
        advBtn.disabled = true;
        advBtn.classList.add('loading');
        const body = document.getElementById('advisor-body');
        body.innerHTML = '<div class="spinner-container"><div class="spinner"></div><div class="spinner-text">AI가 포트폴리오를 분석하고 있습니다...</div></div>';
        try {
          const data = await API.getAdvisor();
          body.innerHTML = this._renderAdvisor(data);
        } catch (err) {
          body.innerHTML = `<div style="color:var(--sell);padding:1rem">분석 실패: ${err.message}</div>`;
        }
        advBtn.disabled = false;
        advBtn.classList.remove('loading');
      });
    }

    // Sell buttons — event delegation
    container.addEventListener('click', (e) => {
      const btn = e.target.closest('.pf-sell-btn');
      if (!btn) return;
      e.stopPropagation();
      const ticker = btn.dataset.ticker;
      const totalQty = parseInt(btn.dataset.totalqty) || 1;
      const reason = btn.dataset.reason || 'manual';
      const currency = btn.dataset.currency || 'USD';
      const card = btn.closest('.pf-card');
      const name = card ? card.querySelector('.pf-card-name')?.textContent || '' : '';
      const curPriceEl = card ? card.querySelector('.pf-price-current') : null;
      const retEl = card ? card.querySelector('.pf-price-return') : null;

      App.openSellModal({
        ticker, name, totalQty, reason, currency,
        avgPrice: btn.dataset.buyprice || '-',
        curPrice: curPriceEl ? curPriceEl.textContent : '-',
        returnText: retEl ? retEl.textContent : '-',
        returnColor: retEl ? retEl.style.color : '',
      });
    });
  },

  _renderAdvisor(data) {
    if (data.error) {
      return `<div style="color:var(--sell);padding:1rem">${data.error}</div>`;
    }

    const urgencyColor = data.urgency === 'high' ? 'var(--sell)' : data.urgency === 'medium' ? 'var(--hold)' : 'var(--buy)';
    const urgencyLabel = data.urgency === 'high' ? 'URGENT' : data.urgency === 'medium' ? 'ATTENTION' : 'NORMAL';

    const actionIcons = { sell: '&#128308;', buy: '&#128994;', hold: '&#128992;', warn: '&#9888;' };
    const actionColors = { sell: 'var(--sell)', buy: 'var(--buy)', hold: 'var(--hold)', warn: 'var(--hold)' };
    const actionBgs = { sell: 'var(--sell-bg)', buy: 'var(--buy-bg)', hold: 'var(--hold-bg)', warn: 'rgba(245,158,11,.08)' };

    const actions = (data.actions || [])
      .sort((a, b) => (b.priority || 0) - (a.priority || 0))
      .map(a => {
        const type = a.type || 'hold';
        const priorityDots = a.priority >= 4 ? ' !!!' : a.priority >= 3 ? ' !!' : '';
        return `
          <div style="display:flex;gap:.75rem;align-items:flex-start;padding:.85rem 1rem;border-radius:var(--radius-sm);border:1px solid ${actionColors[type]}22;background:${actionBgs[type]}">
            <span style="font-size:1.1rem;flex-shrink:0;margin-top:.1rem">${actionIcons[type]}</span>
            <div style="flex:1">
              <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.25rem">
                <strong style="font-size:.9rem;color:${actionColors[type]}">${a.title || ''}${priorityDots}</strong>
                ${a.ticker ? `<span style="font-size:.7rem;padding:.1rem .4rem;border-radius:4px;background:var(--bg-elevated);color:var(--text-muted);font-weight:600;cursor:pointer" onclick="location.hash='#/stock/${a.ticker}'">${a.ticker}</span>` : ''}
              </div>
              <div style="font-size:.83rem;line-height:1.6;color:var(--text-secondary)">${a.detail || ''}</div>
            </div>
          </div>
        `;
      }).join('');

    const marketBadge = data.market_regime || '보통';
    const regimeColor = marketBadge === '하락장' ? 'var(--sell)' : marketBadge === '상승장' ? 'var(--buy)' : 'var(--hold)';

    return `
      <div style="display:flex;flex-direction:column;gap:1rem">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem">
          <div style="font-size:1.05rem;font-weight:700;line-height:1.5">${data.market_summary || ''}</div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <span style="font-size:.7rem;padding:.2rem .6rem;border-radius:999px;font-weight:700;background:${regimeColor}15;color:${regimeColor}">${marketBadge}</span>
            <span style="font-size:.65rem;padding:.2rem .5rem;border-radius:999px;font-weight:700;background:${urgencyColor}15;color:${urgencyColor}">${urgencyLabel}</span>
            ${data.high_confidence_count ? `<span style="font-size:.65rem;padding:.2rem .5rem;border-radius:999px;font-weight:700;background:var(--buy-bg);color:var(--buy)">80%+ ${data.high_confidence_count}</span>` : ''}
          </div>
        </div>
        ${actions ? `<div style="display:flex;flex-direction:column;gap:.5rem">${actions}</div>` : ''}
        ${data.weekly_strategy ? `
          <div style="padding:.85rem 1rem;background:linear-gradient(135deg,rgba(56,189,248,.06),transparent);border:1px solid rgba(56,189,248,.15);border-radius:var(--radius-sm)">
            <div style="font-size:.7rem;font-weight:700;color:var(--accent);text-transform:uppercase;letter-spacing:.04em;margin-bottom:.4rem">THIS WEEK</div>
            <div style="font-size:.85rem;line-height:1.7;color:var(--text-primary)">${data.weekly_strategy}</div>
          </div>
        ` : ''}
        ${data.risk_alert ? `
          <div style="padding:.7rem 1rem;background:var(--sell-bg);border:1px solid rgba(239,68,68,.15);border-radius:var(--radius-sm);display:flex;gap:.5rem;align-items:flex-start">
            <span style="font-size:1rem">&#9888;</span>
            <div style="font-size:.83rem;line-height:1.5;color:var(--sell)">${data.risk_alert}</div>
          </div>
        ` : ''}
        ${data.tip ? `
          <div style="font-size:.78rem;color:var(--text-muted);padding:.5rem 0;border-top:1px solid var(--border);font-style:italic">${data.tip}</div>
        ` : ''}
        ${data.generated_at ? `<div style="font-size:.65rem;color:var(--text-muted);text-align:right">${data.generated_at}</div>` : ''}
      </div>
    `;
  },

  // === Summary KPI ===
  _summarySection(summary, holdings, cumPnl) {
    const section = document.createElement('div');
    section.className = 'pf-section';

    const sellCount = holdings.filter(h => h.signal === 'SELL').length;
    const watchCount = holdings.filter(h => h.signal === 'WATCH').length;
    const totalQty = holdings.reduce((s, h) => s + (h.quantity || 1), 0);
    const avgRet = holdings.length > 0
      ? (holdings.reduce((s, h) => s + (h.return_pct || 0), 0) / holdings.length).toFixed(2)
      : '0';
    const cumPnlVal = cumPnl.length > 0 ? cumPnl[0].cum_pnl : 0;

    const items = [
      { label: 'Holdings', value: totalQty, unit: 'qty', color: 'var(--accent)' },
      { label: 'Unrealized', value: (parseFloat(avgRet) >= 0 ? '+' : '') + avgRet, unit: '%', color: parseFloat(avgRet) >= 0 ? 'var(--buy)' : 'var(--sell)' },
      { label: 'Cum. P&L', value: (cumPnlVal >= 0 ? '+' : '') + Utils.formatNumber(cumPnlVal), unit: '', color: cumPnlVal >= 0 ? 'var(--buy)' : 'var(--sell)' },
      { label: 'Sell Signal', value: sellCount, unit: '', color: sellCount > 0 ? 'var(--sell)' : 'var(--text-muted)' },
      { label: 'Total Trades', value: summary.total_trades || 0, unit: '', color: 'var(--text-primary)' },
      { label: 'Win Rate', value: summary.closed_win_rate || 0, unit: '%', color: (summary.closed_win_rate || 0) >= 60 ? 'var(--buy)' : 'var(--hold)' },
      { label: 'Avg Return', value: (summary.closed_avg_return >= 0 ? '+' : '') + (summary.closed_avg_return || 0), unit: '%', color: (summary.closed_avg_return || 0) >= 0 ? 'var(--buy)' : 'var(--sell)' },
    ];

    section.innerHTML = `
      <div class="strat-kpi-bar">
        ${items.map(it => `
          <div class="strat-kpi-item">
            <div class="strat-kpi-label">${it.label}</div>
            <div class="strat-kpi-value" style="color:${it.color}">${it.value}<span class="strat-kpi-unit">${it.unit}</span></div>
          </div>
        `).join('')}
      </div>
    `;
    return section;
  },

  // === Holdings (Grouped by ticker) ===
  _holdingsSection(grouped) {
    const section = document.createElement('div');
    section.className = 'pf-section';

    if (grouped.length === 0) {
      section.innerHTML = `
        <div class="strat-section-head"><h2 class="strat-section-title">Holdings</h2></div>
        <div class="pf-empty">
          <div class="pf-empty-icon">&#128188;</div>
          <div class="pf-empty-text">No holdings yet</div>
          <div class="pf-empty-hint">Buy stocks from Dashboard or Strategy page</div>
        </div>
      `;
      return section;
    }

    const totalTickers = grouped.length;
    const totalQty = grouped.reduce((s, g) => s + g.total_qty, 0);
    const cards = grouped.map(g => this._groupedCard(g)).join('');
    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">Holdings</h2>
        <span class="strat-section-sub">${totalTickers} stocks &middot; ${totalQty} shares</span>
      </div>
      <div class="pf-holdings-grid">${cards}</div>
    `;
    return section;
  },

  _groupedCard(g) {
    const ret = g.return_pct;
    const retColor = ret != null ? (ret >= 0 ? 'var(--buy)' : 'var(--sell)') : 'var(--text-muted)';
    const retText = ret != null ? `${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%` : '-';
    const pnlText = g.total_pnl != null ? `${g.total_pnl >= 0 ? '+' : ''}${Utils.formatNumber(g.total_pnl)}` : '-';
    const pnlColor = g.total_pnl != null ? (g.total_pnl >= 0 ? 'var(--buy)' : 'var(--sell)') : 'var(--text-muted)';

    const signalClass = g.signal === 'SELL' ? 'pf-signal--sell'
                      : g.signal === 'WATCH' ? 'pf-signal--watch'
                      : 'pf-signal--hold';

    const curPrice = g.current_price != null ? Utils.formatPrice(g.current_price, g.currency) : '-';
    const avgPrice = Utils.formatPrice(g.avg_price, g.currency);

    // Position rows (individual buys)
    const posRows = g.positions.map(p => {
      const pRet = p.return_pct;
      const pRetText = pRet != null ? `${pRet >= 0 ? '+' : ''}${pRet.toFixed(1)}%` : '-';
      const pRetColor = pRet != null ? (pRet >= 0 ? 'var(--buy)' : 'var(--sell)') : 'var(--text-muted)';
      const pDate = (p.buy_date || '').slice(0, 10);
      return `
        <div class="pf-pos-row">
          <span class="pf-pos-date">${pDate}</span>
          <span>${p.quantity}x @ ${Utils.formatPrice(p.buy_price, g.currency)}</span>
          <span style="color:${pRetColor};font-weight:600">${pRetText}</span>
          <span class="pf-pos-days">${p.days_held}d</span>
        </div>
      `;
    }).join('');

    // Sell score bar
    const sellScoreHtml = g.sell_score > 0 ? `
      <div class="pf-card-sellscore">
        <span class="pf-sellscore-label">SELL SCORE</span>
        <div class="pf-sellscore-bar">
          <div class="pf-sellscore-fill" style="width:${Math.min(100, g.sell_score * 10)}%;background:${g.sell_score >= 5 ? 'var(--sell)' : g.sell_score >= 3 ? 'var(--hold)' : 'var(--accent)'}"></div>
        </div>
        <span class="pf-sellscore-val" style="color:${g.sell_score >= 5 ? 'var(--sell)' : g.sell_score >= 3 ? 'var(--hold)' : 'var(--text-secondary)'}">${g.sell_score}/10</span>
      </div>
    ` : '';

    // Signal reasons
    const reasonsHtml = g.signal_reasons.length > 0
      ? `<div class="pf-card-reason">${g.signal_reasons.join(' · ')}</div>`
      : '';

    return `
      <div class="pf-card ${g.signal === 'SELL' ? 'pf-card--alert' : ''}">
        <div class="pf-card-top">
          <div>
            <div class="pf-card-ticker" onclick="location.hash='#/stock/${g.ticker}'">${g.ticker}</div>
            <div class="pf-card-name">${(g.name || '').slice(0, 22)}</div>
          </div>
          <div class="pf-signal ${signalClass}">${g.signal}</div>
        </div>

        <div class="pf-card-prices">
          <div class="pf-price-current">${curPrice}</div>
          <div class="pf-price-return" style="color:${retColor}">${retText}</div>
        </div>

        <div class="pf-card-summary">
          <div class="pf-summary-item">
            <span class="pf-summary-label">Qty</span>
            <span class="pf-summary-value">${g.total_qty}</span>
          </div>
          <div class="pf-summary-item">
            <span class="pf-summary-label">Avg Price</span>
            <span class="pf-summary-value">${avgPrice}</span>
          </div>
          <div class="pf-summary-item">
            <span class="pf-summary-label">Total Cost</span>
            <span class="pf-summary-value">${Utils.formatNumber(g.total_cost)}</span>
          </div>
          <div class="pf-summary-item">
            <span class="pf-summary-label">P&L</span>
            <span class="pf-summary-value" style="color:${pnlColor}">${pnlText}</span>
          </div>
        </div>

        <div class="pf-card-meta">
          ${g.rsi ? `<div class="pf-meta-row"><span>RSI</span><span style="color:${g.rsi > 70 ? 'var(--sell)' : g.rsi < 30 ? 'var(--buy)' : 'var(--text-primary)'}">${g.rsi.toFixed(0)}</span></div>` : ''}
          ${g.volatility ? `<div class="pf-meta-row"><span>Volatility</span><span style="color:${g.volatility > 4 ? 'var(--sell)' : 'var(--text-primary)'}">${g.volatility.toFixed(1)}%</span></div>` : ''}
          ${g.market_regime ? `<div class="pf-meta-row"><span>Market</span><span style="color:${g.market_regime === '하락장' ? 'var(--sell)' : g.market_regime === '상승장' ? 'var(--buy)' : 'var(--text-secondary)'}">${g.market_regime}</span></div>` : ''}
        </div>

        ${sellScoreHtml}
        ${reasonsHtml}

        <!-- Individual positions (collapsed) -->
        ${g.positions.length > 1 ? `
        <div class="pf-positions-toggle" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('hidden')">
          <span>Positions (${g.positions.length})</span>
          <svg class="pf-toggle-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="m6 9 6 6 6-6"/></svg>
        </div>
        <div class="pf-positions-list hidden">
          ${posRows}
        </div>
        ` : `
        <div class="pf-positions-list">
          ${posRows}
        </div>
        `}

        <div class="pf-card-actions">
          <button class="pf-sell-btn ${g.signal === 'SELL' ? 'pf-sell-btn--urgent' : ''}"
            data-ticker="${g.ticker}" data-totalqty="${g.total_qty}"
            data-currency="${g.currency || 'USD'}"
            data-reason="${(g.signal_reasons[0] || 'manual').replace(/"/g, '&quot;')}"
            data-buyprice="${avgPrice}">
            Sell (${g.total_qty} shares)
          </button>
        </div>
      </div>
    `;
  },

  // === Trade History (Buy + Sell) ===
  _historySection(trades) {
    const section = document.createElement('div');
    section.className = 'pf-section';

    if (trades.length === 0) {
      section.innerHTML = `
        <div class="strat-section-head"><h2 class="strat-section-title">Trade History</h2></div>
        <div class="pf-empty-hint" style="text-align:center;padding:1rem;color:var(--text-muted)">No trades yet</div>
      `;
      return section;
    }

    const closedTrades = trades.filter(t => t.status === 'closed');
    const wins = closedTrades.filter(t => (t.return_pct || 0) >= 0).length;
    const winRate = closedTrades.length > 0 ? (wins / closedTrades.length * 100).toFixed(1) : '0';
    const avgRet = closedTrades.length > 0
      ? (closedTrades.reduce((s, t) => s + (t.return_pct || 0), 0) / closedTrades.length).toFixed(2)
      : '0';

    const rows = trades.map(t => {
      const isClosed = t.status === 'closed';
      const ret = t.return_pct;
      const retColor = isClosed ? (ret >= 0 ? 'var(--buy)' : 'var(--sell)') : 'var(--text-muted)';
      const retIcon = isClosed ? (ret >= 0 ? '&#9650;' : '&#9660;') : '';
      const retText = isClosed ? `${retIcon} ${ret >= 0 ? '+' : ''}${ret.toFixed(2)}%` : '-';
      const typeLabel = isClosed
        ? '<span style="color:var(--sell);font-weight:600">SELL</span>'
        : '<span style="color:var(--buy);font-weight:600">BUY</span>';
      const date = isClosed ? t.sell_date : t.buy_date;
      const price = isClosed
        ? `${Utils.formatPrice(t.buy_price, t.currency)} → ${Utils.formatPrice(t.sell_price, t.currency)}`
        : Utils.formatPrice(t.buy_price, t.currency);
      const reason = isClosed ? (t.sell_reason || '-') : '-';

      return `<tr class="strat-tr">
        <td class="strat-td">${typeLabel}</td>
        <td class="strat-td strat-td--ticker">${t.ticker}</td>
        <td class="strat-td">${t.quantity || 1}x</td>
        <td class="strat-td" style="font-size:.8rem">${price}</td>
        <td class="strat-td"><span style="color:${retColor};font-weight:700">${retText}</span></td>
        <td class="strat-td" style="font-size:.75rem;color:var(--text-muted)">${reason}</td>
        <td class="strat-td" style="font-size:.75rem;color:var(--text-muted)">${(date || '').slice(0, 16)}</td>
      </tr>`;
    }).join('');

    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">Trade History</h2>
        <span class="strat-section-sub">
          ${trades.length} trades &middot; Win ${winRate}% &middot; Avg ${parseFloat(avgRet) >= 0 ? '+' : ''}${avgRet}%
        </span>
      </div>
      <div class="strat-card pf-history-scroll">
        <table class="strat-table">
          <thead><tr>
            <th class="strat-th">Type</th><th class="strat-th">Ticker</th>
            <th class="strat-th">Qty</th><th class="strat-th">Price</th>
            <th class="strat-th">Return</th><th class="strat-th">Reason</th>
            <th class="strat-th">Date</th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `;
    return section;
  },
};
