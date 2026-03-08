// === Dashboard View ===

const DashboardView = {
  async render(container) {
    Utils.showSpinner(container, '종목 분석 중...');

    try {
      const res = await API.getRecommendations(50);
      const items = res.recommendations || [];
      container.innerHTML = '';

      // Summary header
      const summary = document.createElement('div');
      summary.className = 'section-title';
      summary.style.marginBottom = '1.5rem';
      const buyCount = items.filter(i => i.recommendation === 'BUY').length;
      const holdCount = items.filter(i => i.recommendation === 'HOLD').length;
      const sellCount = items.filter(i => i.recommendation === 'SELL').length;
      const highConfCount = items.filter(i => i.recommendation === 'BUY' && i.confidence >= 80).length;
      summary.innerHTML = `전체 ${items.length}개 종목 분석 완료 &nbsp;`
        + `<span class="badge badge-buy">매수 ${buyCount}</span> `
        + (highConfCount > 0 ? `<span class="badge badge-buy" style="background:rgba(34,197,94,.2)">80%+ ${highConfCount}</span> ` : '')
        + `<span class="badge badge-hold">보유 ${holdCount}</span> `
        + `<span class="badge badge-sell">매도 ${sellCount}</span>`;
      container.appendChild(summary);

      // Market regime warning
      this._addMarketWarning(container);

      if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">추천 데이터가 없습니다</div>';
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
      container.innerHTML = `<div class="empty-state">데이터 로딩 실패: ${err.message}</div>`;
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
