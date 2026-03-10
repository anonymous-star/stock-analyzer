// === Dashboard View ===

const DashboardView = {
  async render(container) {
    // 진행률 표시 로딩 UI
    container.innerHTML = `
      <div class="dash-loading" id="dash-loading">
        <div class="spinner"></div>
        <div class="spinner-text" id="dash-loading-text">종목 분석 준비 중...</div>
        <div class="dash-progress-bar" id="dash-progress-wrap" style="display:none">
          <div class="dash-progress-fill" id="dash-progress-fill" style="width:0%"></div>
        </div>
        <div class="dash-progress-detail" id="dash-progress-detail" style="font-size:.8rem;color:var(--text-secondary);margin-top:.5rem"></div>
      </div>`;

    // 폴링으로 진행률 표시
    let progressInterval = null;
    try {
      progressInterval = setInterval(async () => {
        try {
          const p = await API._fetch('/recommendations/progress');
          const text = document.getElementById('dash-loading-text');
          const bar = document.getElementById('dash-progress-wrap');
          const fill = document.getElementById('dash-progress-fill');
          const detail = document.getElementById('dash-progress-detail');
          if (!text) return;
          if (p.running && p.total > 0) {
            const pct = Math.round(p.done / p.total * 100);
            text.textContent = `종목 분석 중... (${p.done}/${p.total})`;
            bar.style.display = '';
            fill.style.width = pct + '%';
            detail.textContent = `${pct}% 완료`;
          } else if (p.has_cache) {
            text.textContent = `${p.cached}개 종목 로딩 중...`;
          }
        } catch {}
      }, 1500);

      const res = await API.getRecommendations(300);
      clearInterval(progressInterval);
      const items = res.recommendations || [];
      const totalPool = res.total_pool || items.length;
      container.innerHTML = '';

      // Summary header with refresh button
      const summary = document.createElement('div');
      summary.className = 'section-title';
      summary.style.cssText = 'margin-bottom:1.5rem;display:flex;align-items:center;flex-wrap:wrap;gap:.5rem';
      const buyCount = items.filter(i => i.recommendation === 'BUY').length;
      const holdCount = items.filter(i => i.recommendation === 'HOLD').length;
      const sellCount = items.filter(i => i.recommendation === 'SELL').length;
      const highConfCount = items.filter(i => i.recommendation === 'BUY' && i.confidence >= 80).length;
      const failedCount = totalPool - items.length;
      summary.innerHTML = `<span>전체 ${items.length}/${totalPool}개 종목 분석</span> `
        + `<span class="badge badge-buy">매수 ${buyCount}</span> `
        + (highConfCount > 0 ? `<span class="badge badge-buy" style="background:rgba(34,197,94,.2)">80%+ ${highConfCount}</span> ` : '')
        + `<span class="badge badge-hold">보유 ${holdCount}</span> `
        + `<span class="badge badge-sell">매도 ${sellCount}</span>`
        + (failedCount > 0 ? ` <span class="badge" style="background:rgba(239,68,68,.15);color:var(--sell);font-size:.7rem">${failedCount}개 실패</span>` : '')
        + ` <button id="btn-refresh-recs" class="strat-btn strat-btn--primary" style="margin-left:auto;padding:.3rem .8rem;font-size:.75rem">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="vertical-align:middle;margin-right:3px"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
            새로고침
          </button>`;
      container.appendChild(summary);

      // Refresh button handler
      document.getElementById('btn-refresh-recs').addEventListener('click', async () => {
        clearApiCache('rec');
        DashboardView.render(container);
      });

      // Market regime warning
      this._addMarketWarning(container);

      if (items.length === 0) {
        container.innerHTML += '<div class="empty-state">추천 데이터가 없습니다. 새로고침을 시도하세요.</div>';
        return;
      }

      // Split into groups
      const buyItems = items.filter(i => i.recommendation === 'BUY');
      const holdItems = items.filter(i => i.recommendation === 'HOLD');
      const sellItems = items.filter(i => i.recommendation === 'SELL');

      // High confidence first
      if (buyItems.length > 0) {
        const highConf = buyItems.filter(i => i.confidence >= 80);
        const normalConf = buyItems.filter(i => i.confidence < 80);

        if (highConf.length > 0) {
          container.appendChild(this._section('확신도 80%+ 매수 추천', 'badge-buy', highConf, true));
        }
        if (normalConf.length > 0) {
          container.appendChild(this._section('매수 추천', 'badge-buy', normalConf));
        }
      }
      if (holdItems.length > 0) {
        container.appendChild(this._section('보유 / 관망', 'badge-hold', holdItems));
      }
      if (sellItems.length > 0) {
        container.appendChild(this._section('매도 / 주의', 'badge-sell', sellItems));
      }
    } catch (err) {
      if (progressInterval) clearInterval(progressInterval);
      container.innerHTML = `<div class="empty-state">
        데이터 로딩 실패: ${err.message}
        <br><button onclick="clearApiCache('rec'); DashboardView.render(this.closest('.main-content') || document.getElementById('main-content'))" class="strat-btn strat-btn--primary" style="margin-top:1rem">다시 시도</button>
      </div>`;
    }
  },

  async _addMarketWarning(container) {
    try {
      const data = await API.getMarketRegime();
      const regime = data.market_regime;
      if (regime === '하락장' || regime === '약세장') {
        const warn = document.createElement('div');
        warn.className = 'strat-insight';
        warn.style.marginBottom = '1.5rem';
        const color = regime === '하락장' ? 'var(--sell)' : 'var(--hold)';
        warn.innerHTML = `
          <div class="strat-insight-icon">&#9888;</div>
          <div>
            <strong style="color:${color}">시장 ${regime}</strong> —
            ${regime === '하락장'
              ? '현금 비중을 높이고, 확신도 80%+ 종목만 선별 매수하세요. 손절선을 타이트하게 설정하세요.'
              : '시장이 약세입니다. 신규 매수는 보수적으로, 기존 수익 종목은 일부 익절을 고려하세요.'}
          </div>
        `;
        container.insertBefore(warn, container.children[1] || null);
      }
    } catch (e) {
      // silent - advisor may not be available
    }
  },

  _section(title, badgeClass, items, highlight = false) {
    const section = document.createElement('div');
    section.style.marginBottom = '2rem';

    const header = document.createElement('div');
    header.className = 'section-title';
    header.innerHTML = `${title} <span class="badge ${badgeClass}">${items.length}</span>`;
    section.appendChild(header);

    if (highlight) {
      const hint = document.createElement('div');
      hint.style.cssText = 'font-size:.8rem;color:var(--text-secondary);margin-bottom:.75rem;padding:.5rem .75rem;background:var(--buy-bg);border-radius:var(--radius-xs);border:1px solid rgba(34,197,94,.15)';
      hint.textContent = '10년 백테스트 기반 높은 적중률이 예상되는 종목입니다. 우선 매수를 고려하세요.';
      section.appendChild(hint);
    }

    const grid = document.createElement('div');
    grid.className = 'card-grid';
    items.forEach(item => grid.appendChild(RecCard.render(item)));
    section.appendChild(grid);

    return section;
  },
};
