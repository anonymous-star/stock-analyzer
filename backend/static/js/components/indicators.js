// === Technical Indicators Renderer ===

const Indicators = {
  render(container, data) {
    container.innerHTML = '';

    if (!data || data.error) {
      container.innerHTML = '<div class="empty-state">기술적 지표 데이터가 없습니다</div>';
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'indicator-grid';

    // Moving Averages
    grid.appendChild(this._maCard(data));

    // RSI
    grid.appendChild(this._rsiCard(data));

    // MACD
    grid.appendChild(this._macdCard(data));

    // Bollinger Bands
    grid.appendChild(this._bbCard(data));

    // Signals Summary
    grid.appendChild(this._signalsCard(data));

    container.appendChild(grid);
  },

  _maCard(data) {
    const card = document.createElement('div');
    card.className = 'indicator-card';
    const price = data.current_price;
    const maRows = [
      ['MA20', data.ma20],
      ['MA50', data.ma50],
      ['MA200', data.ma200],
    ].map(([label, val]) => {
      const diff = val && price ? ((price - val) / val * 100).toFixed(2) : null;
      const diffStr = diff != null ? `(${diff >= 0 ? '+' : ''}${diff}%)` : '';
      const color = diff > 0 ? 'var(--buy)' : diff < 0 ? 'var(--sell)' : '';
      return `<div class="indicator-row">
        <span class="indicator-label">${label}</span>
        <span class="indicator-value" style="color:${color}">${val ? Utils.formatNumber(val) : '-'} ${diffStr}</span>
      </div>`;
    }).join('');

    const signals = data.signals || {};
    const trend = signals.ma_trend;
    const trendBadge = Utils.signalBadge(trend, trend === 'bullish' ? '정배열 (상승추세)' : trend === 'bearish' ? '역배열 (하락추세)' : '중립');

    card.innerHTML = `<h3>이동평균선</h3>${maRows}<div class="mt-1">${trendBadge}</div>`;
    return card;
  },

  _rsiCard(data) {
    const card = document.createElement('div');
    card.className = 'indicator-card';
    const rsi = data.rsi;
    const rsiColor = rsi < 30 ? 'var(--buy)' : rsi > 70 ? 'var(--sell)' : 'var(--hold)';
    const signals = data.signals || {};
    const rsiSignal = signals.rsi_signal;
    const badge = Utils.signalBadge(
      rsiSignal === 'oversold' ? 'bullish' : rsiSignal === 'overbought' ? 'bearish' : 'neutral',
      rsiSignal === 'oversold' ? '과매도 (반등 기대)' : rsiSignal === 'overbought' ? '과매수 (주의)' : '중립'
    );

    card.innerHTML = `
      <h3>RSI (14)</h3>
      <div style="font-size:2rem;font-weight:700;color:${rsiColor};margin-bottom:.5rem">${rsi != null ? rsi.toFixed(1) : '-'}</div>
      <div class="progress-bar">
        <div class="progress-fill" style="width:${rsi || 0}%;background:${rsiColor}"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:.7rem;color:var(--text-muted)">
        <span>과매도 30</span><span>중립 50</span><span>과매수 70</span>
      </div>
      <div class="mt-1">${badge}</div>
    `;
    return card;
  },

  _macdCard(data) {
    const card = document.createElement('div');
    card.className = 'indicator-card';
    const macd = data.macd || {};
    const signals = data.signals || {};
    const macdSignal = signals.macd_signal;
    const badge = Utils.signalBadge(macdSignal, macdSignal === 'bullish' ? '골든크로스' : macdSignal === 'bearish' ? '데드크로스' : '중립');

    card.innerHTML = `
      <h3>MACD</h3>
      <div class="indicator-row">
        <span class="indicator-label">MACD</span>
        <span class="indicator-value">${macd.macd != null ? macd.macd.toFixed(4) : '-'}</span>
      </div>
      <div class="indicator-row">
        <span class="indicator-label">Signal</span>
        <span class="indicator-value">${macd.signal != null ? macd.signal.toFixed(4) : '-'}</span>
      </div>
      <div class="indicator-row">
        <span class="indicator-label">Histogram</span>
        <span class="indicator-value" style="color:${(macd.histogram || 0) >= 0 ? 'var(--buy)' : 'var(--sell)'}">
          ${macd.histogram != null ? macd.histogram.toFixed(4) : '-'}
        </span>
      </div>
      <div class="mt-1">${badge}</div>
    `;
    return card;
  },

  _bbCard(data) {
    const card = document.createElement('div');
    card.className = 'indicator-card';
    const bb = data.bollinger_bands || {};
    const signals = data.signals || {};
    const bbPos = signals.bb_position;
    const badge = Utils.signalBadge(
      bbPos === 'below_lower' ? 'bullish' : bbPos === 'above_upper' ? 'bearish' : 'neutral',
      bbPos === 'below_lower' ? '하단 이탈 (반등 가능)' : bbPos === 'above_upper' ? '상단 돌파 (과열)' : '밴드 내'
    );

    card.innerHTML = `
      <h3>볼린저 밴드</h3>
      <div class="indicator-row">
        <span class="indicator-label">상단</span>
        <span class="indicator-value">${bb.upper != null ? Utils.formatNumber(bb.upper) : '-'}</span>
      </div>
      <div class="indicator-row">
        <span class="indicator-label">중단 (MA20)</span>
        <span class="indicator-value">${bb.mid != null ? Utils.formatNumber(bb.mid) : '-'}</span>
      </div>
      <div class="indicator-row">
        <span class="indicator-label">하단</span>
        <span class="indicator-value">${bb.lower != null ? Utils.formatNumber(bb.lower) : '-'}</span>
      </div>
      <div class="mt-1">${badge}</div>
    `;
    return card;
  },

  _signalsCard(data) {
    const card = document.createElement('div');
    card.className = 'indicator-card';
    const signals = data.signals || {};
    const overall = signals.overall_signal;
    const badge = Utils.signalBadge(overall, overall === 'bullish' ? '강세' : overall === 'bearish' ? '약세' : '중립');

    card.innerHTML = `
      <h3>종합 시그널</h3>
      <div style="margin-bottom:.75rem">${badge}</div>
      <div class="indicator-row">
        <span class="indicator-label">현재가</span>
        <span class="indicator-value">${Utils.formatNumber(data.current_price)}</span>
      </div>
      <div class="indicator-row">
        <span class="indicator-label">데이터 기간</span>
        <span class="indicator-value">${data.data_points || '-'}일</span>
      </div>
    `;
    return card;
  },
};
