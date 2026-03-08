// === Utility functions ===

const Utils = {
  formatPrice(price, currency) {
    if (price == null) return '-';
    if (currency === 'KRW') {
      return Math.round(price).toLocaleString('ko-KR') + '원';
    }
    return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  },

  formatChange(pct) {
    if (pct == null) return '';
    const sign = pct >= 0 ? '+' : '';
    return sign + pct.toFixed(2) + '%';
  },

  changeClass(pct) {
    if (pct == null) return '';
    return pct >= 0 ? 'change-up' : 'change-down';
  },

  confidenceTier(confidence) {
    if (confidence >= 80) return '매우 강력';
    if (confidence >= 70) return '강력';
    if (confidence >= 55) return '양호';
    return '보통';
  },

  confidenceColor(confidence) {
    if (confidence >= 80) return 'var(--buy)';
    if (confidence >= 70) return '#ff6b35';
    if (confidence >= 55) return 'var(--hold)';
    return 'var(--text-muted)';
  },

  recBadgeClass(rec) {
    if (rec === 'BUY') return 'rec-badge-buy';
    if (rec === 'SELL') return 'rec-badge-sell';
    return 'rec-badge-hold';
  },

  recLabel(rec) {
    if (rec === 'BUY') return '매수';
    if (rec === 'SELL') return '매도';
    return '보유';
  },

  scoreColor(score) {
    if (score >= 8) return 'var(--buy)';
    if (score >= 5) return '#ff6b35';
    if (score >= 0) return 'var(--hold)';
    if (score >= -5) return 'var(--text-secondary)';
    return 'var(--sell)';
  },

  signalBadge(signal, label) {
    let cls = 'signal-neutral';
    if (signal === 'bullish' || signal === 'oversold' || signal === 'below_lower') cls = 'signal-bullish';
    else if (signal === 'bearish' || signal === 'overbought' || signal === 'above_upper') cls = 'signal-bearish';
    return `<span class="signal-badge ${cls}">${label}</span>`;
  },

  el(tag, attrs, ...children) {
    const e = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === 'className') e.className = v;
        else if (k === 'onclick') e.onclick = v;
        else if (k === 'innerHTML') e.innerHTML = v;
        else e.setAttribute(k, v);
      }
    }
    for (const c of children) {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c) e.appendChild(c);
    }
    return e;
  },

  showSpinner(container, text = '로딩 중...') {
    container.innerHTML = `
      <div class="spinner-container">
        <div class="spinner"></div>
        <div class="spinner-text">${text}</div>
      </div>`;
  },

  debounce(fn, ms) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  },

  formatNumber(n) {
    if (n == null) return '-';
    if (typeof n !== 'number') return String(n);
    return n.toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  },

  formatPercent(n) {
    if (n == null) return '-';
    return (n * 100).toFixed(1) + '%';
  },

  stepperChange(btn, dir) {
    const stepper = btn.closest('.stepper');
    if (!stepper) return;
    const input = stepper.querySelector('input[type="number"]');
    if (!input) return;
    const step = parseFloat(input.step) || 1;
    const min = input.min !== '' ? parseFloat(input.min) : -Infinity;
    const max = input.max !== '' ? parseFloat(input.max) : Infinity;
    let val = parseFloat(input.value) || 0;
    val = dir > 0 ? Math.min(max, +(val + step).toFixed(4)) : Math.max(min, +(val - step).toFixed(4));
    input.value = val;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  },
};
