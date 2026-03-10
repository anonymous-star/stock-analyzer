// === Strategy View (v2 UI) ===

const StrategyView = {
  _cache: null,

  async render(container) {
    if (this._cache) {
      container.innerHTML = '';
      container.appendChild(this._cache.cloneNode(true));
      this._bindEvents();
      return;
    }

    Utils.showSpinner(container, '10년 백테스트 기반 전략 분석 중...');

    try {
      const [recsRes, bt20, bt40, bt60] = await Promise.all([
        API.getRecommendations(300),
        API.getBacktest(20, 300),
        API.getBacktest(40, 300),
        API.getBacktest(60, 300),
      ]);

      const recs = recsRes.recommendations || [];
      const bt20Results = bt20.results || [];
      const btMap = {};
      bt20Results.forEach(r => { btMap[r.ticker] = r; });

      // Aggregate stats for KPI
      const kpi = this._calcKPI(bt20Results, recs);

      container.innerHTML = '';
      const frag = document.createElement('div');
      frag.className = 'strategy-dashboard';

      // 0. KPI Summary Bar
      frag.appendChild(this._kpiSection(kpi));

      // 1. ML Model + Cache
      frag.appendChild(await this._mlModelSection());

      // 2. Hold Period Comparison
      frag.appendChild(this._holdPeriodSection(bt20, bt40, bt60));

      // 3. Two-column: Top Stocks + Current Signals
      const twoCol = document.createElement('div');
      twoCol.className = 'strat-two-col';
      twoCol.appendChild(this._topStocksSection(bt20Results));
      twoCol.appendChild(this._currentSignalsSection(recs, btMap));
      frag.appendChild(twoCol);

      // 4. Strategy Summary
      frag.appendChild(this._strategySummary(recs, btMap, kpi));

      container.appendChild(frag);
      this._cache = frag.cloneNode(true);
      this._bindEvents();
    } catch (err) {
      container.innerHTML = `<div class="empty-state">전략 분석 실패: ${err.message}</div>`;
    }
  },

  _bindEvents() {
    const btn = document.getElementById('btn-train-model');
    const status = document.getElementById('train-status');
    if (btn && !btn._bound) {
      btn._bound = true;
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.classList.add('loading');
        status.textContent = '학습 중... (1~3분 소요)';
        status.style.color = 'var(--text-secondary)';
        try {
          const data = await API._post('/model/train');
          if (data.error) {
            status.textContent = '학습 실패: ' + data.error;
            status.style.color = 'var(--sell)';
          } else {
            const oppBase = data.opportunity_baseline || '?';
            status.innerHTML = `<span style="color:var(--buy)">학습 완료!</span> AUC ${data.auc} · 수익기회 ${oppBase}% · ${data.train_duration_sec}초`;
            status.style.color = 'var(--text-primary)';
            StrategyView._cache = null;
            clearApiCache('model-info');
            clearApiCache('rec');
            clearApiCache('bt');
          }
        } catch (e) {
          status.textContent = '학습 실패: ' + e.message;
          status.style.color = 'var(--sell)';
        }
        btn.disabled = false;
        btn.classList.remove('loading');
      });
    }
  },

  // === KPI Calculation ===
  _calcKPI(bt20Results, recs) {
    let totalBuy = 0, totalHits = 0, totalRet = 0;
    let opp1Total = 0, opp1Count = 0;
    let slRetTotal = 0;
    bt20Results.forEach(r => {
      const bc = r.buy.count;
      totalBuy += bc;
      totalHits += Math.round(r.buy.hit_rate * bc / 100);
      totalRet += r.buy.avg_return * bc;
      const opp = r.buy_opportunity || {};
      if (bc > 0 && opp.opportunity_1pct !== undefined) {
        opp1Total += opp.opportunity_1pct * bc / 100;
        opp1Count += bc;
        slRetTotal += (opp.sl_avg_return || 0) * bc;
      }
    });
    const buys = recs.filter(r => r.recommendation === 'BUY');
    return {
      totalSignals: totalBuy,
      hitRate: totalBuy ? (totalHits / totalBuy * 100).toFixed(1) : '0',
      avgReturn: totalBuy ? (totalRet / totalBuy).toFixed(2) : '0',
      oppRate: opp1Count ? (opp1Total / opp1Count * 100).toFixed(1) : '0',
      slReturn: totalBuy ? (slRetTotal / totalBuy).toFixed(2) : '0',
      currentBuys: buys.length,
      totalStocks: bt20Results.length,
    };
  },

  // === Section 0: KPI Summary ===
  _kpiSection(kpi) {
    const section = document.createElement('div');
    section.className = 'strat-kpi-bar';
    const items = [
      { label: '분석 종목', value: kpi.totalStocks, unit: '개', color: 'var(--accent)' },
      { label: 'BUY 시그널', value: kpi.totalSignals.toLocaleString(), unit: '건', color: 'var(--text-primary)' },
      { label: '종료시 적중률', value: kpi.hitRate, unit: '%', color: parseFloat(kpi.hitRate) >= 60 ? 'var(--buy)' : 'var(--hold)' },
      { label: '1%+ 수익 기회', value: kpi.oppRate, unit: '%', color: parseFloat(kpi.oppRate) >= 80 ? 'var(--buy)' : 'var(--hold)' },
      { label: '만기 수익률', value: (parseFloat(kpi.avgReturn) >= 0 ? '+' : '') + kpi.avgReturn, unit: '%', color: parseFloat(kpi.avgReturn) >= 0 ? 'var(--buy)' : 'var(--sell)' },
      { label: '동적SL 수익', value: (parseFloat(kpi.slReturn) >= 0 ? '+' : '') + kpi.slReturn, unit: '%', color: parseFloat(kpi.slReturn) >= 0 ? 'var(--buy)' : 'var(--sell)' },
      { label: '현재 BUY', value: kpi.currentBuys, unit: '종목', color: 'var(--buy)' },
    ];
    section.innerHTML = items.map(it => `
      <div class="strat-kpi-item">
        <div class="strat-kpi-label">${it.label}</div>
        <div class="strat-kpi-value" style="color:${it.color}">${it.value}<span class="strat-kpi-unit">${it.unit}</span></div>
      </div>
    `).join('');
    return section;
  },

  // === Section 1: ML Model ===
  async _mlModelSection() {
    const section = document.createElement('div');
    section.className = 'strat-section';

    let modelInfo = null, cacheStats = null;
    try { modelInfo = await API.getModelInfo(); } catch (e) {}
    try { cacheStats = await API._fetch('/cache/stats'); } catch (e) {}

    const hasModel = modelInfo && modelInfo.status === 'ready';

    let inner = '';
    if (hasModel) {
      const imp = modelInfo.feature_importance || {};
      const maxImp = Math.max(...Object.values(imp), 1);
      const topFeatures = Object.entries(imp).slice(0, 8);
      const impBars = topFeatures.map(([k, v]) => {
        const pct = (v / maxImp * 100).toFixed(0);
        const label = this._featureLabel(k);
        return `<div class="strat-feat-row">
          <span class="strat-feat-name">${label}</span>
          <div class="strat-feat-bar"><div class="strat-feat-fill" style="width:${pct}%"></div></div>
          <span class="strat-feat-val">${v}</span>
        </div>`;
      }).join('');

      const opp80 = modelInfo.opportunity_80_plus || [];
      const oppRows = opp80.slice(0, 4).map(o => `
        <tr>
          <td class="strat-td">품질 ${o.min_quality}+${o.max_risk === 'any' ? '' : ', 위험 ' + o.max_risk + '이하'}</td>
          <td class="strat-td"><strong style="color:var(--buy)">${o.opportunity_rate}%</strong></td>
          <td class="strat-td">${o.count}건</td>
          <td class="strat-td">+${o.avg_max_return}%</td>
        </tr>
      `).join('');

      inner = `
        <div class="strat-ml-grid">
          <div class="strat-card strat-card--accent">
            <div class="strat-card-header">
              <span class="strat-card-icon">&#9881;</span>
              <span>모델 상태</span>
              <span class="strat-status-dot strat-status-dot--active"></span>
            </div>
            <div class="strat-ml-stats">
              <div class="strat-ml-stat">
                <div class="strat-ml-stat-val">${modelInfo.auc}</div>
                <div class="strat-ml-stat-label">AUC</div>
              </div>
              <div class="strat-ml-stat">
                <div class="strat-ml-stat-val" style="color:var(--buy)">${modelInfo.opportunity_baseline || 0}%</div>
                <div class="strat-ml-stat-label">수익 기회</div>
              </div>
              <div class="strat-ml-stat">
                <div class="strat-ml-stat-val">${modelInfo.total_samples || 0}</div>
                <div class="strat-ml-stat-label">학습 데이터</div>
              </div>
              <div class="strat-ml-stat">
                <div class="strat-ml-stat-val">${modelInfo.trained_at || '-'}</div>
                <div class="strat-ml-stat-label">학습일시</div>
              </div>
            </div>
          </div>
          <div class="strat-card">
            <div class="strat-card-header"><span class="strat-card-icon">&#128202;</span><span>피처 중요도</span></div>
            <div class="strat-feat-list">${impBars}</div>
          </div>
        </div>
        ${oppRows ? `
        <div class="strat-card" style="margin-top:.75rem">
          <div class="strat-card-header"><span class="strat-card-icon">&#127919;</span><span>80%+ 수익 기회 필터</span></div>
          <table class="strat-table">
            <thead><tr><th class="strat-th">조건</th><th class="strat-th">수익 기회</th><th class="strat-th">샘플</th><th class="strat-th">최대 수익</th></tr></thead>
            <tbody>${oppRows}</tbody>
          </table>
        </div>` : ''}`;
    } else {
      inner = `
        <div class="strat-card strat-card--muted">
          <div class="strat-card-header"><span class="strat-card-icon">&#9881;</span><span>ML 모델</span></div>
          <p style="color:var(--text-secondary);margin:.75rem 0">모델이 아직 학습되지 않았습니다. 아래 버튼으로 학습하면 확신도 예측 정확도가 향상됩니다.</p>
        </div>`;
    }

    const cacheInfo = cacheStats
      ? `<span class="strat-cache-info">캐시: ${cacheStats.history_entries}건 가격 / ${cacheStats.info_entries}건 정보 (${cacheStats.db_size_mb}MB)</span>`
      : '';

    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">ML 모델</h2>
        <div class="strat-section-actions">
          <button id="btn-train-model" class="strat-btn strat-btn--primary">
            ${hasModel ? '재학습' : '학습 시작'}
          </button>
          <span id="train-status" class="strat-train-status"></span>
          ${cacheInfo}
        </div>
      </div>
      ${inner}
    `;
    return section;
  },

  _featureLabel(key) {
    const map = {
      quality_score: '품질 점수', ticker_rolling_hit_rate: '종목 적중률',
      risk_flags: '위험 플래그', score: '원점수', volatility: '변동성',
      trend_20d: '20일 추세', rsi: 'RSI', ma20_slope: 'MA20 기울기',
      macd_accel: 'MACD 가속', bb_width: 'BB 폭', vol_ratio: '거래량 비율',
      mom5: '5일 모멘텀', market_breadth: '시장 breadth',
      market_trend_20d: '시장 추세', market_volatility: '시장 변동성',
      rsi_vol_interaction: 'RSI×변동성', trend_quality: '추세 품질',
      score_volatility_adj: '변동성 조정 점수', mean_reversion_signal: '평균회귀',
      ticker_signal_count: '시그널 수', ticker_recent_hit_rate: '최근 적중률',
      ticker_rolling_avg_return: '종목 평균 수익', bb_rsi_squeeze: 'BB-RSI 스퀴즈',
      down_streak: '연속 하락', rsi_change: 'RSI 변화',
      market_above_ma20: '시장>MA20', market_above_ma50: '시장>MA50',
      market_above_ma200: '시장>MA200',
    };
    return map[key] || key;
  },

  // === Section 2: Hold Period ===
  _holdPeriodSection(bt20, bt40, bt60) {
    const section = document.createElement('div');
    section.className = 'strat-section';

    const allBt = [
      { days: 20, results: bt20.results || [] },
      { days: 40, results: bt40.results || [] },
      { days: 60, results: bt60.results || [] },
    ];

    const rows = allBt.map(({ days, results }) => {
      const agg = { count: 0, hits: 0, totalRet: 0, opp1: 0, slRet: 0, opp1Count: 0 };
      results.forEach(r => {
        const bc = r.buy.count;
        agg.count += bc;
        agg.hits += Math.round(r.buy.hit_rate * bc / 100);
        agg.totalRet += r.buy.avg_return * bc;
        const opp = r.buy_opportunity || {};
        if (bc > 0 && opp.opportunity_1pct !== undefined) {
          agg.opp1 += opp.opportunity_1pct * bc / 100;
          agg.opp1Count += bc;
          agg.slRet += (opp.sl_avg_return || 0) * bc;
        }
      });
      return {
        days,
        count: agg.count,
        hitRate: agg.count ? (agg.hits / agg.count * 100) : 0,
        avgRet: agg.count ? (agg.totalRet / agg.count) : 0,
        opp1: agg.opp1Count ? (agg.opp1 / agg.opp1Count * 100) : 0,
        slRet: agg.count ? (agg.slRet / agg.count) : 0,
      };
    });

    const best = rows.reduce((a, b) => {
      const sa = a.hitRate * 0.5 + a.avgRet * 2;
      const sb = b.hitRate * 0.5 + b.avgRet * 2;
      return sb > sa ? b : a;
    });

    const cardRows = rows.map(r => {
      const isBest = r.days === best.days;
      return `
        <div class="strat-hold-card${isBest ? ' strat-hold-card--best' : ''}">
          <div class="strat-hold-days">${r.days}일${isBest ? ' <span class="strat-best-badge">최적</span>' : ''}</div>
          <div class="strat-hold-metrics">
            <div class="strat-hold-metric">
              <div class="strat-hold-metric-val">${r.count.toLocaleString()}</div>
              <div class="strat-hold-metric-label">BUY 건수</div>
            </div>
            <div class="strat-hold-metric">
              <div class="strat-hold-metric-val" style="color:${r.hitRate >= 60 ? 'var(--buy)' : r.hitRate >= 55 ? 'var(--hold)' : 'var(--text-primary)'}">${r.hitRate.toFixed(1)}%</div>
              <div class="strat-hold-metric-label">적중률</div>
              <div class="strat-mini-bar"><div class="strat-mini-fill" style="width:${r.hitRate}%;background:${r.hitRate >= 60 ? 'var(--buy)' : 'var(--hold)'}"></div></div>
            </div>
            <div class="strat-hold-metric">
              <div class="strat-hold-metric-val" style="color:${r.opp1 >= 80 ? 'var(--buy)' : 'var(--hold)'}">${r.opp1.toFixed(1)}%</div>
              <div class="strat-hold-metric-label">수익 기회</div>
              <div class="strat-mini-bar"><div class="strat-mini-fill" style="width:${r.opp1}%;background:${r.opp1 >= 80 ? 'var(--buy)' : 'var(--hold)'}"></div></div>
            </div>
            <div class="strat-hold-metric">
              <div class="strat-hold-metric-val" style="color:${r.avgRet >= 0 ? 'var(--buy)' : 'var(--sell)'}">${r.avgRet >= 0 ? '+' : ''}${r.avgRet.toFixed(2)}%</div>
              <div class="strat-hold-metric-label">만기 수익</div>
            </div>
            <div class="strat-hold-metric">
              <div class="strat-hold-metric-val" style="color:${r.slRet >= 0 ? 'var(--buy)' : 'var(--sell)'}">${r.slRet >= 0 ? '+' : ''}${r.slRet.toFixed(2)}%</div>
              <div class="strat-hold-metric-label">동적SL 수익</div>
            </div>
          </div>
        </div>
      `;
    }).join('');

    const r20 = rows.find(r => r.days === 20) || rows[0];
    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">보유 기간별 성과</h2>
        <span class="strat-section-sub">10년 백테스트 기반</span>
      </div>
      <div class="strat-hold-grid">${cardRows}</div>
      <div class="strat-insight">
        <div class="strat-insight-icon">&#128161;</div>
        <div>
          <strong>수익 전략:</strong>
          BUY 시그널의 <strong style="color:var(--buy)">${r20.opp1.toFixed(1)}%</strong>가 20일 내 1%+ 수익 기회 제공.
          동적 손절(변동성 기반 -3~-7%) 적용 시 수익을 무제한으로 유지하면서 손실만 제한합니다.
        </div>
      </div>
    `;
    return section;
  },

  // === Section 3: Top Stocks ===
  _topStocksSection(results) {
    const section = document.createElement('div');
    section.className = 'strat-section';

    const qualified = results.filter(r => r.buy.count >= 10);
    const byCombo = [...qualified]
      .map(r => ({ ...r, combo: r.buy.hit_rate * 0.6 + r.buy.avg_return * 4 }))
      .sort((a, b) => b.combo - a.combo)
      .slice(0, 10);

    const tableRows = byCombo.map((r, i) => {
      const hitPct = r.buy.hit_rate;
      const hitColor = hitPct >= 70 ? 'var(--buy)' : hitPct >= 60 ? 'var(--hold)' : 'var(--text-primary)';
      const retColor = r.buy.avg_return >= 0 ? 'var(--buy)' : 'var(--sell)';
      return `<tr class="strat-tr" onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
        <td class="strat-td strat-td--rank">${i + 1}</td>
        <td class="strat-td strat-td--ticker">${r.ticker}</td>
        <td class="strat-td">
          <div class="strat-hit-wrap">
            <span style="color:${hitColor};font-weight:700">${hitPct}%</span>
            <div class="strat-mini-bar strat-mini-bar--wide"><div class="strat-mini-fill" style="width:${hitPct}%;background:${hitColor}"></div></div>
          </div>
        </td>
        <td class="strat-td"><span style="color:${retColor};font-weight:600">${r.buy.avg_return >= 0 ? '+' : ''}${r.buy.avg_return}%</span></td>
        <td class="strat-td">${r.buy.count}</td>
        <td class="strat-td">${r.accuracy}%</td>
      </tr>`;
    }).join('');

    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">10년 검증 우수 종목</h2>
        <span class="strat-section-sub">BUY 10건+ 종합 순위</span>
      </div>
      <div class="strat-card">
        <table class="strat-table">
          <thead><tr>
            <th class="strat-th">#</th><th class="strat-th">종목</th>
            <th class="strat-th">BUY 적중률</th><th class="strat-th">평균수익</th>
            <th class="strat-th">건수</th><th class="strat-th">전체 적중</th>
          </tr></thead>
          <tbody>${tableRows}</tbody>
        </table>
      </div>
    `;
    return section;
  },

  // === Section 4: Current Signals ===
  _currentSignalsSection(recs, btMap) {
    const section = document.createElement('div');
    section.className = 'strat-section';

    const buys = recs.filter(r => r.recommendation === 'BUY');
    const nearBuys = recs.filter(r => r.recommendation === 'HOLD' && r.score >= 3)
      .sort((a, b) => b.score - a.score).slice(0, 10);

    const renderSignalCard = (r) => {
      const bt = btMap[r.ticker];
      const btHit = bt ? bt.buy.hit_rate : null;
      const btCount = bt ? bt.buy.count : 0;
      const verified = btHit >= 65 && btCount >= 10;
      const changeCls = Utils.changeClass(r.change_percent);
      const confColor = Utils.confidenceColor(r.confidence);

      return `<div class="strat-signal-card${verified ? ' strat-signal-card--verified' : ''}" onclick="location.hash='#/stock/${r.ticker}'">
        <div class="strat-signal-header">
          <div>
            <div class="strat-signal-ticker">${r.ticker}</div>
            <div class="strat-signal-name">${(r.name || '').slice(0, 20)}</div>
          </div>
          <span class="rec-badge ${Utils.recBadgeClass(r.recommendation)}">${Utils.recLabel(r.recommendation)}</span>
        </div>
        <div class="strat-signal-body">
          <div class="strat-signal-price">
            ${Utils.formatPrice(r.current_price, r.currency)}
            <span class="${changeCls}" style="font-size:.8rem">${Utils.formatChange(r.change_percent)}</span>
          </div>
          <div class="strat-signal-metrics">
            <div><span class="strat-signal-metric-label">확신도</span><span style="color:${confColor};font-weight:700">${r.confidence}%</span></div>
            <div><span class="strat-signal-metric-label">점수</span><span style="font-weight:600">+${r.score}</span></div>
            <div><span class="strat-signal-metric-label">RSI</span><span>${r.rsi ? r.rsi.toFixed(0) : '-'}</span></div>
            <div><span class="strat-signal-metric-label">10년</span><span style="color:${btHit >= 65 ? 'var(--buy)' : btHit != null ? 'var(--hold)' : 'var(--text-muted)'};font-weight:600">${btHit != null ? btHit + '%' : 'N/A'}</span></div>
          </div>
        </div>
        ${verified ? '<div class="strat-verified-tag">10년 검증</div>' : ''}
        ${r.trade_guide ? `<div class="strat-trade-guide">TP ${r.trade_guide.take_profit}% / SL ${r.trade_guide.stop_loss}% / ${r.trade_guide.hold_days}d</div>` : ''}
        ${r.recommendation === 'BUY' ? `
          <button class="rec-card-buy-btn strat-buy-btn" style="margin-top:.5rem"
            onclick="event.stopPropagation(); App.openBuyModal('${r.ticker}', '${(r.name || '').replace(/'/g, "\\'")}', ${r.current_price}, '${r.currency || 'USD'}')">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
            Buy
          </button>
        ` : ''}
      </div>`;
    };

    const renderNearRow = (r) => {
      const bt = btMap[r.ticker];
      const btHit = bt ? bt.buy.hit_rate : null;
      const btCount = bt ? bt.buy.count : 0;
      const changeCls = Utils.changeClass(r.change_percent);
      return `<tr class="strat-tr" onclick="location.hash='#/stock/${r.ticker}'" style="cursor:pointer">
        <td class="strat-td strat-td--ticker">${r.ticker}</td>
        <td class="strat-td">+${r.score}</td>
        <td class="strat-td">${Utils.formatPrice(r.current_price, r.currency)} <span class="${changeCls}" style="font-size:.75rem">${Utils.formatChange(r.change_percent)}</span></td>
        <td class="strat-td">${r.rsi ? r.rsi.toFixed(0) : '-'}</td>
        <td class="strat-td">${btHit != null ? `<span style="color:${btHit >= 65 ? 'var(--buy)' : 'var(--hold)'};font-weight:600">${btHit}%</span> <span style="font-size:.7rem;color:var(--text-muted)">(${btCount})</span>` : '-'}</td>
      </tr>`;
    };

    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">현재 시그널</h2>
        <span class="strat-section-sub">실시간 × 10년 교차 검증</span>
      </div>
      ${buys.length > 0 ? `
        <div class="strat-subsection-head"><span class="strat-badge strat-badge--buy">BUY ${buys.length}</span></div>
        <div class="strat-signal-grid">${buys.map(renderSignalCard).join('')}</div>
      ` : '<div class="strat-empty-hint">현재 BUY 시그널 없음</div>'}
      ${nearBuys.length > 0 ? `
        <div class="strat-subsection-head" style="margin-top:1.5rem"><span class="strat-badge strat-badge--hold">BUY 근접 ${nearBuys.length}</span></div>
        <div class="strat-card">
          <table class="strat-table">
            <thead><tr><th class="strat-th">종목</th><th class="strat-th">점수</th><th class="strat-th">현재가</th><th class="strat-th">RSI</th><th class="strat-th">10년 적중</th></tr></thead>
            <tbody>${nearBuys.map(renderNearRow).join('')}</tbody>
          </table>
        </div>
      ` : ''}
    `;
    return section;
  },

  // === Section 5: Strategy Summary ===
  _strategySummary(recs, btMap, kpi) {
    const buys = recs.filter(r => r.recommendation === 'BUY');
    const nearBuys = recs.filter(r => r.recommendation === 'HOLD' && r.score >= 3);
    const totalRecs = recs.length;
    const buyPct = (buys.length / totalRecs * 100).toFixed(1);

    const verifiedBuys = buys.filter(r => {
      const bt = btMap[r.ticker];
      return bt && bt.buy.hit_rate >= 65 && bt.buy.count >= 10;
    });
    const oversoldCandidates = nearBuys.filter(r => {
      const bt = btMap[r.ticker];
      return r.rsi && r.rsi < 35 && bt && bt.buy.hit_rate >= 60 && bt.buy.count >= 10;
    });
    const verifiedNear = nearBuys.filter(r => {
      const bt = btMap[r.ticker];
      return bt && bt.buy.hit_rate >= 65 && bt.buy.count >= 10;
    });

    const section = document.createElement('div');
    section.className = 'strat-section';

    let actionItems = [];

    // Market sentiment
    const sentiment = buyPct < 10 ? '약세장 — 선별 매수' : buyPct < 25 ? '보통 시장' : '강세장 — 적극 매수';
    const sentColor = buyPct < 10 ? 'var(--sell)' : buyPct < 25 ? 'var(--hold)' : 'var(--buy)';

    if (verifiedBuys.length > 0) {
      const list = verifiedBuys.map(r => {
        const bt = btMap[r.ticker];
        return `<strong>${r.ticker}</strong>(${bt.buy.hit_rate}%)`;
      }).join(', ');
      actionItems.push({ icon: '&#10004;', text: `10년 검증 BUY: ${list}`, type: 'positive' });
    }

    if (oversoldCandidates.length > 0) {
      const list = oversoldCandidates.slice(0, 3).map(r => `<strong>${r.ticker}</strong>(RSI ${r.rsi.toFixed(0)})`).join(', ');
      actionItems.push({ icon: '&#128269;', text: `과매도 관찰: ${list} — 반등 시 매수 대기`, type: 'watch' });
    }

    if (verifiedNear.length > 0) {
      const list = verifiedNear.slice(0, 3).map(r => `<strong>${r.ticker}</strong>(+${r.score})`).join(', ');
      actionItems.push({ icon: '&#9200;', text: `BUY 근접 + 검증: ${list} — 전환 시 진입`, type: 'watch' });
    }

    actionItems.push({ icon: '&#128176;', text: `손절: 변동성 기반 동적SL (-3~-7%) / 익절: 제한 없음 / 최대 보유 20일`, type: 'info' });
    actionItems.push({ icon: '&#128202;', text: `포트폴리오: 종목당 <strong>8%</strong> 이내 / 최대 동시 보유 <strong>12종목</strong>`, type: 'info' });

    const actionHtml = actionItems.map(a => `
      <div class="strat-action-item strat-action-item--${a.type}">
        <span class="strat-action-icon">${a.icon}</span>
        <span>${a.text}</span>
      </div>
    `).join('');

    section.innerHTML = `
      <div class="strat-section-head">
        <h2 class="strat-section-title">전략 요약</h2>
      </div>
      <div class="strat-summary-top">
        <div class="strat-market-sentiment">
          <span class="strat-sentiment-label">시장 상태</span>
          <span class="strat-sentiment-value" style="color:${sentColor}">${sentiment}</span>
          <span class="strat-sentiment-detail">전체 ${totalRecs}종목 중 BUY ${buys.length}개 (${buyPct}%)</span>
        </div>
      </div>
      <div class="strat-actions">${actionHtml}</div>
    `;
    return section;
  },
};
