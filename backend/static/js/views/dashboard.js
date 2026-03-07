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
      summary.innerHTML = `전체 ${items.length}개 종목 분석 완료 &nbsp;`
        + `<span class="badge badge-buy">매수 ${buyCount}</span> `
        + `<span class="badge badge-hold">보유 ${holdCount}</span> `
        + `<span class="badge badge-sell">매도 ${sellCount}</span>`;
      container.appendChild(summary);

      if (items.length === 0) {
        container.innerHTML = '<div class="empty-state">추천 데이터가 없습니다</div>';
        return;
      }

      // Split into groups
      const buyItems = items.filter(i => i.recommendation === 'BUY');
      const holdItems = items.filter(i => i.recommendation === 'HOLD');
      const sellItems = items.filter(i => i.recommendation === 'SELL');

      if (buyItems.length > 0) {
        container.appendChild(this._section('매수 추천', 'badge-buy', buyItems));
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

  _section(title, badgeClass, items) {
    const section = document.createElement('div');
    section.style.marginBottom = '2rem';

    const header = document.createElement('div');
    header.className = 'section-title';
    header.innerHTML = `${title} <span class="badge ${badgeClass}">${items.length}</span>`;
    section.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'card-grid';
    items.forEach(item => grid.appendChild(RecCard.render(item)));
    section.appendChild(grid);

    return section;
  },
};
