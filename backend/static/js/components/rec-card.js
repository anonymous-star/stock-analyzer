// === Recommendation Card Renderer ===

const RecCard = {
  render(item) {
    const { el, formatPrice, formatChange, changeClass, recBadgeClass, recLabel,
            scoreColor, confidenceTier, confidenceColor } = Utils;

    const card = el('div', { className: 'rec-card', onclick: () => location.hash = `#/stock/${item.ticker}` });

    // Header: name + badge
    const recText = `${recLabel(item.recommendation)} ${item.confidence}%`;
    card.innerHTML = `
      <div class="rec-card-header">
        <div class="rec-card-info">
          <h3>${item.name || item.ticker}</h3>
          <span class="ticker">${item.ticker}</span>
        </div>
        <span class="rec-badge ${recBadgeClass(item.recommendation)}">${recText}</span>
      </div>

      <div class="rec-card-price">
        <span class="price">${formatPrice(item.current_price, item.currency)}</span>
        <span class="change ${changeClass(item.change_percent)}">${formatChange(item.change_percent)}</span>
      </div>

      <div class="rec-card-score">
        <div class="score-bar">
          <div class="score-bar-fill" style="width: ${Math.max(0, (item.score + 17) / 41 * 100)}%; background: ${scoreColor(item.score)};"></div>
        </div>
        <span class="score-label">${item.score >= 0 ? '+' : ''}${item.score}/${item.max_score}</span>
        <span class="confidence-label" style="color: ${confidenceColor(item.confidence)}">
          ${confidenceTier(item.confidence)}
        </span>
      </div>

      ${this._renderChips(item)}

      <div class="rec-card-metrics">
        <div class="metric">
          <div class="metric-label">RSI</div>
          <div class="metric-value">${item.rsi != null ? item.rsi.toFixed(1) : '-'}</div>
        </div>
        <div class="metric">
          <div class="metric-label">MA</div>
          <div class="metric-value">${item.ma_trend === 'bullish' ? '정배열' : item.ma_trend === 'bearish' ? '역배열' : '-'}</div>
        </div>
        <div class="metric">
          <div class="metric-label">PER</div>
          <div class="metric-value">${item.pe_ratio != null ? item.pe_ratio.toFixed(1) : '-'}</div>
        </div>
        <div class="metric">
          <div class="metric-label">거래량</div>
          <div class="metric-value">${item.volume_ratio != null ? item.volume_ratio.toFixed(1) + 'x' : '-'}</div>
        </div>
      </div>
    `;

    return card;
  },

  _renderChips(item) {
    if (!item.score_breakdown) return '';
    const bd = item.score_breakdown;
    const chips = [
      { label: '기술', value: bd.technical },
      { label: '재무', value: bd.financial },
      { label: '거래량', value: bd.volume },
      { label: '모멘텀', value: bd.momentum },
    ];
    if (bd.news) chips.push({ label: '뉴스', value: bd.news });

    return `<div class="rec-card-chips">${chips.map(c => {
      const cls = c.value > 0 ? 'chip-positive' : c.value < 0 ? 'chip-negative' : '';
      return `<span class="chip ${cls}">${c.label} ${c.value >= 0 ? '+' : ''}${c.value}</span>`;
    }).join('')}</div>`;
  },
};
