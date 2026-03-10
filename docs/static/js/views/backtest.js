// === Backtest View ===

const BacktestView = {
  _holdDays: 20,
  _analysisCache: null,

  async render(container, holdDays) {
    if (holdDays) this._holdDays = holdDays;
    container.innerHTML = '';

    // Hold period analysis section (top)
    const analysisSection = document.createElement('div');
    analysisSection.id = 'hold-analysis';
    container.appendChild(analysisSection);

    // Separator
    const sep = document.createElement('hr');
    sep.style.cssText = 'border:none;border-top:1px solid var(--border);margin:2rem 0';
    container.appendChild(sep);

    // Title
    const title = document.createElement('div');
    title.className = 'section-title';
    title.textContent = '종목별 백테스트';
    container.appendChild(title);

    // Controls
    const controls = document.createElement('div');
    controls.className = 'backtest-controls';
    controls.innerHTML = '<label>보유 기간:</label>';

    [10, 20, 30, 40, 60].forEach(days => {
      const btn = document.createElement('button');
      btn.className = 'hold-btn' + (days === this._holdDays ? ' active' : '');
      btn.textContent = days + '일';
      btn.onclick = () => {
        this._holdDays = days;
        this._loadStockResults(document.getElementById('backtest-results'), days);
        controls.querySelectorAll('.hold-btn').forEach((b, i) =>
          b.classList.toggle('active', [10, 20, 30, 40, 60][i] === days));
      };
      controls.appendChild(btn);
    });
    container.appendChild(controls);

    // Results area
    const resultsDiv = document.createElement('div');
    resultsDiv.id = 'backtest-results';
    container.appendChild(resultsDiv);

    // Load both sections
    this._loadHoldAnalysis(analysisSection);
    this._loadStockResults(resultsDiv, this._holdDays);
  },

  _renderAnalysisFromCache(container, rows) {
    container.innerHTML = '';

    const title = document.createElement('div');
    title.className = 'section-title';
    title.textContent = '보유 기간별 성과 분석';
    container.appendChild(title);

    const desc = document.createElement('p');
    desc.style.cssText = 'color:var(--text-secondary);font-size:.85rem;margin-bottom:1.25rem';
    desc.textContent = '확신도 티어별 BUY 시그널의 적중률과 평균 수익률을 보유 기간별로 비교합니다.';
    container.appendChild(desc);

    const tierNames = ['매우 강력', '강력', '양호', '보통'];
    const table = document.createElement('div');
    table.className = 'analysis-table-wrap';
    table.innerHTML = this._buildAnalysisTable(rows, tierNames);
    container.appendChild(table);

    container.appendChild(this._buildInsightCard(rows, tierNames));
  },

  _aggregateRows(allData, periods) {
    return periods.map((days, idx) => {
      const results = allData[idx].results || [];
      const tiers = {};
      const tierNames = ['매우 강력', '강력', '양호', '보통'];
      tierNames.forEach(t => { tiers[t] = { count: 0, hits: 0, totalRet: 0 }; });

      results.forEach(r => {
        Object.entries(r.buy_tiers || {}).forEach(([tier, stats]) => {
          if (tiers[tier]) {
            tiers[tier].count += stats.count;
            tiers[tier].hits += Math.round(stats.hit_rate * stats.count / 100);
            tiers[tier].totalRet += stats.avg_return * stats.count;
          }
        });
      });

      return { days, tiers, tierNames };
    });
  },

  async _loadHoldAnalysis(container) {
    if (this._analysisCache) {
      this._renderAnalysisFromCache(container, this._analysisCache);
      return;
    }

    const periods = [10, 20, 30, 40, 60];
    const statusDiv = document.createElement('div');
    statusDiv.className = 'spinner-container';
    container.innerHTML = '<div class="section-title">보유 기간별 성과 분석</div>';
    container.appendChild(statusDiv);

    try {
      // Load sequentially with progress
      const allData = [];
      for (let i = 0; i < periods.length; i++) {
        statusDiv.innerHTML = `
          <div class="spinner"></div>
          <div class="spinner-text">10년 백테스트 수집 중... ${periods[i]}일 보유 (${i + 1}/${periods.length})</div>`;
        allData.push(await API.getBacktest(periods[i], 300));
      }

      const rows = this._aggregateRows(allData, periods);
      this._analysisCache = rows;
      this._renderAnalysisFromCache(container, rows);
    } catch (err) {
      container.innerHTML = `<div class="empty-state">보유 기간 분석 실패: ${err.message}</div>`;
    }
  },

  _buildAnalysisTable(rows, tierNames) {
    const headerCells = tierNames.map(t =>
      `<th colspan="2" class="tier-col-header">${t}</th>`
    ).join('');

    const subHeaders = tierNames.map(() =>
      `<th class="sub-header">적중률</th><th class="sub-header">평균수익</th>`
    ).join('');

    const bodyRows = rows.map(r => {
      const cells = tierNames.map(tier => {
        const t = r.tiers[tier];
        if (t.count === 0) return '<td class="at-cell">-</td><td class="at-cell">-</td>';
        const hitRate = (t.hits / t.count * 100).toFixed(1);
        const avgRet = (t.totalRet / t.count).toFixed(2);
        const hitColor = hitRate >= 80 ? 'var(--buy)' : hitRate >= 65 ? 'var(--hold)' : hitRate >= 50 ? 'var(--text-primary)' : 'var(--sell)';
        const retColor = avgRet >= 0 ? 'var(--buy)' : 'var(--sell)';
        return `<td class="at-cell"><span style="color:${hitColor};font-weight:600">${hitRate}%</span><span class="at-count">${t.count}건</span></td>
                <td class="at-cell"><span style="color:${retColor};font-weight:600">${avgRet >= 0 ? '+' : ''}${avgRet}%</span></td>`;
      }).join('');
      return `<tr><td class="at-cell at-period">${r.days}일</td>${cells}</tr>`;
    }).join('');

    return `<table class="analysis-table">
      <thead>
        <tr><th class="at-cell at-period">보유기간</th>${headerCells}</tr>
        <tr><th></th>${subHeaders}</tr>
      </thead>
      <tbody>${bodyRows}</tbody>
    </table>`;
  },

  _buildInsightCard(rows, tierNames) {
    // Find best period for "매우 강력"
    let bestPeriod = null;
    let bestScore = -Infinity;
    rows.forEach(r => {
      const t = r.tiers['매우 강력'];
      if (t.count > 0) {
        const hit = t.hits / t.count * 100;
        const avg = t.totalRet / t.count;
        const score = hit * 0.5 + avg * 2; // weighted score
        if (score > bestScore) {
          bestScore = score;
          bestPeriod = r;
        }
      }
    });

    const card = document.createElement('div');
    card.className = 'insight-card';

    let insights = [];

    if (bestPeriod) {
      const t = bestPeriod.tiers['매우 강력'];
      const hit = (t.hits / t.count * 100).toFixed(1);
      const avg = (t.totalRet / t.count).toFixed(2);
      insights.push(`"매우 강력" BUY는 <strong>${bestPeriod.days}일 보유</strong>가 최적 (적중률 ${hit}%, 평균 +${avg}%)`);
    }

    // Find best for each tier
    tierNames.slice(1).forEach(tier => {
      let best = null, bScore = -Infinity;
      rows.forEach(r => {
        const t = r.tiers[tier];
        if (t.count >= 5) {
          const hit = t.hits / t.count * 100;
          const avg = t.totalRet / t.count;
          const s = hit * 0.4 + avg * 1.5;
          if (s > bScore) { bScore = s; best = r; }
        }
      });
      if (best) {
        const t = best.tiers[tier];
        const hit = (t.hits / t.count * 100).toFixed(1);
        const avg = (t.totalRet / t.count).toFixed(2);
        insights.push(`"${tier}" BUY → <strong>${best.days}일 보유</strong> 권장 (적중률 ${hit}%, 평균 ${avg >= 0 ? '+' : ''}${avg}%)`);
      }
    });

    // General warning for 60-day
    const d60 = rows.find(r => r.days === 60);
    if (d60) {
      const t60 = d60.tiers['매우 강력'];
      if (t60.count > 0) {
        const hit60 = (t60.hits / t60.count * 100).toFixed(1);
        if (hit60 < 65) {
          insights.push(`60일 이상 보유 시 "매우 강력"도 적중률 ${hit60}%로 하락 — 장기 보유 주의`);
        }
      }
    }

    card.innerHTML = `
      <h3>분석 인사이트</h3>
      <ul>${insights.map(i => `<li>${i}</li>`).join('')}</ul>
    `;
    return card;
  },

  async _loadStockResults(resultsDiv, holdDays) {
    Utils.showSpinner(resultsDiv, '백테스트 실행 중...');

    try {
      const res = await API.getBacktest(holdDays, 300);
      const results = res.results || [];
      resultsDiv.innerHTML = '';

      if (results.length === 0) {
        resultsDiv.innerHTML = '<div class="empty-state">백테스트 결과가 없습니다</div>';
        return;
      }

      const avgAcc = (results.reduce((s, r) => s + r.accuracy, 0) / results.length).toFixed(1);
      const s = res.summary || {};
      const summary = document.createElement('div');
      summary.className = 'backtest-summary-box';
      summary.innerHTML = `
        <div class="section-title" style="margin-bottom:1rem">총 ${results.length}개 종목 (${holdDays}일 보유)</div>
        <div class="backtest-stats">
          <div class="backtest-stat">
            <div class="backtest-stat-label">BUY 시그널</div>
            <div class="backtest-stat-value">${s.total_signals || 0}건</div>
          </div>
          <div class="backtest-stat">
            <div class="backtest-stat-label">익절 적중률</div>
            <div class="backtest-stat-value" style="color:var(--buy)">${s.tp_hit_rate || 0}%</div>
            <div class="backtest-stat-sub">+1% TP 도달 (SL 전)</div>
          </div>
          <div class="backtest-stat">
            <div class="backtest-stat-label">만기 적중률</div>
            <div class="backtest-stat-value">${s.hit_rate || 0}%</div>
            <div class="backtest-stat-sub">${holdDays}일 후 수익 비율</div>
          </div>
          <div class="backtest-stat">
            <div class="backtest-stat-label">3%+ 수익 기회</div>
            <div class="backtest-stat-value" style="color:var(--buy)">${s.opportunity_3pct || 0}%</div>
            <div class="backtest-stat-sub">보유 중 3%+ 도달</div>
          </div>
          <div class="backtest-stat">
            <div class="backtest-stat-label">손절 적용 수익</div>
            <div class="backtest-stat-value" style="color:${(s.sl_avg_return||0) >= 0 ? 'var(--buy)' : 'var(--sell)'}">${(s.sl_avg_return||0) >= 0 ? '+' : ''}${s.sl_avg_return || 0}%</div>
            <div class="backtest-stat-sub">동적 손절 적용 시</div>
          </div>
        </div>`;
      resultsDiv.appendChild(summary);

      results.forEach(item => resultsDiv.appendChild(this._renderCard(item)));
    } catch (err) {
      resultsDiv.innerHTML = `<div class="empty-state">백테스트 실패: ${err.message}</div>`;
    }
  },

  _renderCard(item) {
    const card = document.createElement('div');
    card.className = 'backtest-card';

    const accColor = item.accuracy >= 60 ? 'var(--buy)' : item.accuracy >= 50 ? 'var(--hold)' : 'var(--sell)';
    const avgColor = item.avg_return >= 0 ? 'var(--buy)' : 'var(--sell)';

    let tiersHtml = '';
    if (item.buy_tiers && Object.keys(item.buy_tiers).length > 0) {
      tiersHtml = `
        <div style="margin-top:.75rem">
          <div style="font-size:.85rem;color:var(--text-secondary);margin-bottom:.5rem">확신도 티어별 BUY 성과</div>
          <div class="tier-grid">
            ${Object.entries(item.buy_tiers).map(([tier, stats]) => {
              const hitColor = stats.hit_rate >= 60 ? 'var(--buy)' : stats.hit_rate >= 50 ? 'var(--hold)' : 'var(--sell)';
              return `<div class="tier-card">
                <div class="tier-name">${tier}</div>
                <div class="tier-hit" style="color:${hitColor}">${stats.hit_rate}%</div>
                <div class="tier-count">${stats.count}건 / 평균 ${stats.avg_return >= 0 ? '+' : ''}${stats.avg_return}%</div>
              </div>`;
            }).join('')}
          </div>
        </div>
      `;
    }

    card.innerHTML = `
      <div class="backtest-card-header">
        <h3>${item.name || item.ticker} <span style="color:var(--text-muted);font-weight:400">${item.ticker}</span></h3>
        <div class="backtest-accuracy" style="color:${accColor}">${item.accuracy}%</div>
      </div>

      <div class="backtest-stats">
        <div class="backtest-stat">
          <div class="backtest-stat-label">BUY 신호</div>
          <div class="backtest-stat-value" style="color:var(--buy)">${item.buy.count}건</div>
          <div class="backtest-stat-sub">적중률 ${item.buy.hit_rate}% / 평균 ${item.buy.avg_return >= 0 ? '+' : ''}${item.buy.avg_return}%</div>
        </div>
        <div class="backtest-stat">
          <div class="backtest-stat-label">HOLD 신호</div>
          <div class="backtest-stat-value" style="color:var(--hold)">${item.hold.count}건</div>
          <div class="backtest-stat-sub">적중률 ${item.hold.hit_rate}% / 평균 ${item.hold.avg_return >= 0 ? '+' : ''}${item.hold.avg_return}%</div>
        </div>
        <div class="backtest-stat">
          <div class="backtest-stat-label">SELL 신호</div>
          <div class="backtest-stat-value" style="color:var(--sell)">${item.sell.count}건</div>
          <div class="backtest-stat-sub">적중률 ${item.sell.hit_rate}% / 평균 ${item.sell.avg_return >= 0 ? '+' : ''}${item.sell.avg_return}%</div>
        </div>
      </div>

      <div class="indicator-row" style="padding:.5rem 0">
        <span class="indicator-label">총 시그널 수</span>
        <span class="indicator-value">${item.total_signals}건</span>
      </div>
      <div class="indicator-row" style="padding:.5rem 0">
        <span class="indicator-label">전체 평균 수익률</span>
        <span class="indicator-value" style="color:${avgColor}">${item.avg_return >= 0 ? '+' : ''}${item.avg_return}%</span>
      </div>
      ${item.buy_opportunity ? `
      <div class="indicator-row" style="padding:.5rem 0">
        <span class="indicator-label">1%+ 수익 기회</span>
        <span class="indicator-value" style="color:var(--buy)">${item.buy_opportunity.opportunity_1pct}%</span>
      </div>
      <div class="indicator-row" style="padding:.5rem 0">
        <span class="indicator-label">3%+ 수익 기회</span>
        <span class="indicator-value" style="color:var(--buy)">${item.buy_opportunity.opportunity_3pct}%</span>
      </div>
      <div class="indicator-row" style="padding:.5rem 0">
        <span class="indicator-label">손절 적용 수익</span>
        <span class="indicator-value" style="color:${item.buy_opportunity.sl_avg_return >= 0 ? 'var(--buy)' : 'var(--sell)'}">${item.buy_opportunity.sl_avg_return >= 0 ? '+' : ''}${item.buy_opportunity.sl_avg_return}%</span>
      </div>` : ''}

      ${tiersHtml}
    `;

    return card;
  },
};
