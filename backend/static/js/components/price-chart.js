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

      this._chart = LightweightCharts.createChart(chartDiv, {
        width: chartDiv.clientWidth,
        height: 400,
        layout: {
          background: { type: 'solid', color: '#1e293b' },
          textColor: '#94a3b8',
        },
        grid: {
          vertLines: { color: 'rgba(51,65,85,.5)' },
          horzLines: { color: 'rgba(51,65,85,.5)' },
        },
        crosshair: { mode: 0 },
        rightPriceScale: { borderColor: '#334155' },
        timeScale: { borderColor: '#334155' },
      });

      this._series = this._chart.addAreaSeries({
        topColor: 'rgba(99,102,241,.4)',
        bottomColor: 'rgba(99,102,241,.05)',
        lineColor: '#6366f1',
        lineWidth: 2,
      });

      this._series.setData(data);
      this._chart.timeScale().fitContent();

      // Resize observer
      const ro = new ResizeObserver(() => {
        if (this._chart) {
          this._chart.applyOptions({ width: chartDiv.clientWidth });
        }
      });
      ro.observe(chartDiv);
    } catch (err) {
      chartDiv.innerHTML = `<div class="empty-state">차트 데이터를 불러올 수 없습니다: ${err.message}</div>`;
    }
  },
};
