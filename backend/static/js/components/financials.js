// === Financials Renderer ===

const Financials = {
  render(container, data) {
    container.innerHTML = '';

    if (!data) {
      container.innerHTML = '<div class="empty-state">재무 데이터가 없습니다</div>';
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'financial-grid';

    // Valuation
    const val = data.valuation || {};
    grid.appendChild(this._card('밸류에이션', [
      ['PER', val.pe_ratio != null ? val.pe_ratio.toFixed(1) + '배' : '-'],
      ['PBR', val.pb_ratio != null ? val.pb_ratio.toFixed(2) + '배' : '-'],
      ['PEG', val.peg_ratio != null ? val.peg_ratio.toFixed(2) : '-'],
      ['PSR', val.ps_ratio != null ? val.ps_ratio.toFixed(2) + '배' : '-'],
      ['EV/EBITDA', val.ev_to_ebitda != null ? val.ev_to_ebitda.toFixed(1) : '-'],
    ]));

    // Profitability
    const prof = data.profitability || {};
    grid.appendChild(this._card('수익성', [
      ['순이익률', prof.profit_margin != null ? (prof.profit_margin * 100).toFixed(1) + '%' : '-'],
      ['영업이익률', prof.operating_margin != null ? (prof.operating_margin * 100).toFixed(1) + '%' : '-'],
      ['ROE', prof.roe != null ? (prof.roe * 100).toFixed(1) + '%' : '-'],
      ['ROA', prof.roa != null ? (prof.roa * 100).toFixed(1) + '%' : '-'],
    ]));

    // Growth
    const growth = data.growth || {};
    grid.appendChild(this._card('성장률', [
      ['매출 성장률', growth.revenue_growth != null ? (growth.revenue_growth * 100).toFixed(1) + '%' : '-'],
      ['이익 성장률', growth.earnings_growth != null ? (growth.earnings_growth * 100).toFixed(1) + '%' : '-'],
    ]));

    // Financial Health
    const health = data.financial_health || {};
    grid.appendChild(this._card('재무상태', [
      ['부채비율', health.debt_to_equity != null ? health.debt_to_equity.toFixed(1) + '%' : '-'],
      ['유동비율', health.current_ratio != null ? health.current_ratio.toFixed(2) : '-'],
      ['배당수익률', health.dividend_yield != null ? (health.dividend_yield * 100).toFixed(2) + '%' : '-'],
    ]));

    // Company Info
    const info = data.company_info || {};
    if (info.sector || info.industry) {
      grid.appendChild(this._card('기업정보', [
        ['섹터', info.sector || '-'],
        ['산업', info.industry || '-'],
        ['시가총액', this._formatMarketCap(info.market_cap)],
      ]));
    }

    container.appendChild(grid);
  },

  _card(title, rows) {
    const card = document.createElement('div');
    card.className = 'financial-card';
    const rowsHtml = rows.map(([label, value]) =>
      `<div class="indicator-row">
        <span class="indicator-label">${label}</span>
        <span class="indicator-value">${value}</span>
      </div>`
    ).join('');
    card.innerHTML = `<h3>${title}</h3>${rowsHtml}`;
    return card;
  },

  _formatMarketCap(val) {
    if (val == null) return '-';
    if (val >= 1e12) return (val / 1e12).toFixed(1) + '조';
    if (val >= 1e8) return (val / 1e8).toFixed(0) + '억';
    if (val >= 1e9) return (val / 1e9).toFixed(1) + 'B';
    if (val >= 1e6) return (val / 1e6).toFixed(0) + 'M';
    return val.toLocaleString();
  },
};
