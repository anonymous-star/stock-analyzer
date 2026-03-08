// === Price Chart (TradingView Lightweight Charts) ===

const PriceChart = {
  _chart: null,
  _series: null,

  async render(container, ticker, period = '6mo') {
    container.innerHTML = '';

    const wrapper = document.createElement('div');
    wrapper.className = 'chart-container';

    // Period buttons
    const periods = ['1mo', '3mo', '6mo', '1y', '2y'];
    const btnRow = document.createElement('div');
    btnRow.className = 'period-btns';
    periods.forEach(p => {
      const btn = document.createElement('button');
      btn.className = 'period-btn' + (p === period ? ' active' : '');
      btn.textContent = p;
      btn.onclick = () => this.render(container, ticker, p);
      btnRow.appendChild(btn);
    });
    wrapper.appendChild(btnRow);

    // Chart div
    const chartDiv = document.createElement('div');
    chartDiv.style.height = '400px';
    wrapper.appendChild(chartDiv);
    container.appendChild(wrapper);

    // Fetch data
    try {
      const res = await API.getHistory(ticker, period);
      const data = res.data.map(d => ({
        time: d.date.split('T')[0],
        value: d.close,
      }));

      if (this._chart) {
        this._chart.remove();
        this._chart = null;
      }

      const cs = getComputedStyle(document.documentElement);
      const chartBg = cs.getPropertyValue('--chart-bg').trim() || '#1a1f2e';
      const chartGrid = cs.getPropertyValue('--chart-grid').trim() || '#334155';
      const chartText = cs.getPropertyValue('--chart-text').trim() || '#94a3b8';

      this._chart = LightweightCharts.createChart(chartDiv, {
        width: chartDiv.clientWidth,
        height: 400,
        layout: {
          background: { type: 'solid', color: chartBg },
          textColor: chartText,
        },
        grid: {
          vertLines: { color: chartGrid + '80' },
          horzLines: { color: chartGrid + '80' },
        },
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: chartGrid },
        timeScale: { borderColor: chartGrid },
      });

      this._series = this._chart.addAreaSeries({
        topColor: 'rgba(56,189,248,.3)',
        bottomColor: 'rgba(56,189,248,.02)',
        lineColor: '#38bdf8',
        lineWidth: 2,
      });

      this._series.setData(data);
      this._chart.timeScale().fitContent();

      // Resize observer (disconnect previous)
      if (this._resizeObserver) {
        this._resizeObserver.disconnect();
      }
      this._resizeObserver = new ResizeObserver(() => {
        if (this._chart) {
          this._chart.applyOptions({ width: chartDiv.clientWidth });
        }
      });
      this._resizeObserver.observe(chartDiv);
    } catch (err) {
      chartDiv.innerHTML = `<div class="empty-state">차트 데이터를 불러올 수 없습니다: ${err.message}</div>`;
    }
  },
};
