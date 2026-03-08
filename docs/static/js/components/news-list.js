// === News List Renderer ===

const NewsList = {
  render(container, data) {
    container.innerHTML = '';

    if (!data || !data.news || data.news.length === 0) {
      container.innerHTML = '<div class="empty-state">뉴스가 없습니다</div>';
      return;
    }

    const list = document.createElement('div');
    list.className = 'news-list';

    data.news.forEach(item => {
      const card = document.createElement('div');
      card.className = 'news-card';

      const link = item.link ? `<a href="${item.link}" target="_blank" rel="noopener">${this._escapeHtml(item.title)}</a>` : `<span>${this._escapeHtml(item.title)}</span>`;

      card.innerHTML = `
        ${link}
        ${item.summary ? `<p style="margin-top:.35rem;font-size:.85rem;color:var(--text-secondary);line-height:1.5">${this._escapeHtml(item.summary)}</p>` : ''}
        <div class="news-meta">
          ${item.source ? `<span>${this._escapeHtml(item.source)}</span>` : ''}
          ${item.published ? `<span>${this._formatDate(item.published)}</span>` : ''}
        </div>
      `;
      list.appendChild(card);
    });

    container.appendChild(list);
  },

  _escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  _formatDate(dateStr) {
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diff = now - d;
      if (diff < 3600000) return Math.floor(diff / 60000) + '분 전';
      if (diff < 86400000) return Math.floor(diff / 3600000) + '시간 전';
      if (diff < 604800000) return Math.floor(diff / 86400000) + '일 전';
      return d.toLocaleDateString('ko-KR');
    } catch {
      return dateStr;
    }
  },
};
