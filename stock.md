# Building a dual-market stock screener in Python

**The optimal approach combines pykrx and FinanceDataReader for Korean market data, yfinance for US fundamentals, pandas-ta or the `ta` library for technical indicators, and mplfinance/plotly for visualization—all free and open-source.** This stack lets you screen both KOSPI/KOSDAQ and S&P 500 stocks on valuation metrics (PER, PBR, ROE, EV/EBITDA, DCF) and technical signals (moving averages, RSI, MACD, golden cross) without any paid API keys. The key architectural insight is to use bulk-query APIs for initial filtering, then fetch detailed fundamentals only for candidates that pass the first screen, minimizing API calls and rate-limit problems.

---

## Korean market data: pykrx and FinanceDataReader lead the way

Two libraries dominate Korean stock data access. **pykrx** (v1.0.51, May 2025) scrapes KRX and Naver Finance directly, offering the critical ability to query fundamentals for the *entire market in a single call*. **FinanceDataReader** (v0.9.96) covers multiple global exchanges and adds financial statement retrieval via its `SnapDataReader` API.

**pykrx** excels at bulk screening. A single call to `stock.get_market_fundamental("20250228", market="ALL")` returns PER, PBR, EPS, BPS, and dividend yield for every listed stock at once—ideal for the first-pass valuation filter. It also provides bulk OHLCV and market-cap data. However, pykrx does *not* provide ROE or EV/EBITDA directly; these must be calculated from financial statements or fetched from yfinance.

```python
from pykrx import stock

# Bulk fundamentals for all KOSPI+KOSDAQ stocks
fundamentals = stock.get_market_fundamental("20250228", market="ALL")
# Columns: BPS, PER, PBR, EPS, DIV, DPS — indexed by ticker

# Historical OHLCV for a single stock
ohlcv = stock.get_market_ohlcv("20240101", "20250228", "005930")

# All KOSPI tickers
kospi_tickers = stock.get_market_ticker_list(market="KOSPI")
```

**FinanceDataReader** complements pykrx with richer metadata (sector, industry, listing date) via `fdr.StockListing('KRX')` and full financial statements through `fdr.SnapDataReader('NAVER/FINSTATE/005930')`. This makes it the better choice when you need income statements and balance sheets to compute ROE or EV/EBITDA from scratch.

For **yfinance with Korean tickers** (`.KS` for KOSPI, `.KQ` for KOSDAQ), the `ticker.info` dictionary provides ROE, EV/EBITDA, and financial statements directly—data that pykrx lacks. The tradeoff is that yfinance must be called one stock at a time and is aggressively rate-limited by Yahoo. The recommended pattern is a two-stage approach: use pykrx for bulk PER/PBR screening, then call yfinance only for the **50–100 candidates** that survive the initial filter to get ROE and EV/EBITDA.

**OpenDartReader** deserves mention for official DART/FSS filings. It requires a free API key from opendart.fss.or.kr (10,000 calls/day) and provides audited financial statements—the most reliable source for computing valuation ratios from Korean corporate data.

| Feature | pykrx | FinanceDataReader | yfinance (.KS/.KQ) |
|---------|-------|-------------------|---------------------|
| Bulk market query | ✅ One call | ✅ StockListing | ❌ One-by-one |
| PER, PBR | ✅ Direct | Via SnapDataReader | ✅ Direct |
| ROE | ❌ Must compute | Via financial stmts | ✅ Direct |
| EV/EBITDA | ❌ Not available | Via financial stmts | ✅ Direct |
| Financial statements | ❌ No | ✅ Yes | ✅ Yes |
| Rate limits | Low risk | Low risk | Aggressive |

---

## US market data: yfinance remains the workhorse despite fragility

For S&P 500 screening, **yfinance** (v0.2.66+) remains the dominant free option, but it has experienced significant instability in 2024–2025. Starting from v0.2.59, it switched to `curl_cffi` as a mandatory dependency to bypass Yahoo Finance's TLS fingerprinting. A February 2025 API change caused widespread "possibly delisted" errors. The library now raises `YfRateLimitError` when throttled, and shared hosting environments are particularly affected.

Despite these issues, yfinance's `ticker.info` dictionary provides **all five target metrics** directly: `trailingPE`, `priceToBook`, `returnOnEquity`, `enterpriseToEbitda`, and `freeCashflow`. Financial statements are accessible through `.income_stmt`, `.balance_sheet`, and `.cashflow` properties.

```python
import yfinance as yf
import pandas as pd

# Get S&P 500 ticker list from Wikipedia
sp500 = pd.read_html(
    'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
)[0]
tickers = sp500['Symbol'].tolist()

# Fetch fundamentals for one stock
aapl = yf.Ticker("AAPL")
info = aapl.info
pe = info.get('trailingPE')          # P/E ratio
pb = info.get('priceToBook')          # P/B ratio
roe = info.get('returnOnEquity')      # ROE (decimal)
ev_ebitda = info.get('enterpriseToEbitda')  # EV/EBITDA
fcf = info.get('freeCashflow')        # Free cash flow
```

Key workarounds for yfinance reliability: pin your version in `requirements.txt`, add **0.5–1 second delays** between calls, use `yf.download()` for batch OHLCV instead of individual `Ticker.history()` calls, and implement retry logic with exponential backoff. Caching results to local CSV or SQLite eliminates redundant fetches.

**Alternative free sources** include FinanceToolkit (uses FinancialModelingPrep's free tier at 250 requests/day, excellent for 150+ pre-computed ratios), Alpha Vantage (reduced to just 25 free calls/day—too restrictive for screening), and yahoo_fin as a fallback when yfinance financial statements return empty DataFrames. The pandas-datareader library is effectively abandoned (last release July 2021) and should not be used for Yahoo data.

---

## Technical indicators: three viable libraries and a manual fallback

Three libraries handle the required indicators (50/200-day MA, RSI-14, MACD-12/26/9, golden cross detection). **TA-Lib** is the fastest and most battle-tested (150+ indicators, C core), but requires installing the underlying C library, which can be painful on some systems. **pandas-ta** offers 130+ indicators as a pure-Python Pandas extension with multiprocessing support, though the original maintainer has warned it may be archived by July 2026 without additional support—a community-maintained fork called **pandas-ta-classic** (v0.4.23, January 2026) has emerged as a successor. The **`ta` library** (bukosabino/ta) provides 40+ indicators with a simple API and zero C dependencies.

For a stock screener, pandas-ta or the `ta` library is recommended over TA-Lib because they avoid the C compilation headaches and integrate cleanly with Pandas DataFrames.

```python
# Option A: Using the ta library (pip install ta)
from ta.trend import SMAIndicator, MACD
from ta.momentum import RSIIndicator

df['SMA_50'] = SMAIndicator(close=df['Close'], window=50).sma_indicator()
df['SMA_200'] = SMAIndicator(close=df['Close'], window=200).sma_indicator()
df['RSI'] = RSIIndicator(close=df['Close'], window=14).rsi()
macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
df['MACD'] = macd.macd()
df['MACD_signal'] = macd.macd_signal()
df['MACD_hist'] = macd.macd_diff()

# Option B: Using pandas-ta (pip install pandas-ta)
import pandas_ta as ta
df.ta.sma(length=50, append=True)
df.ta.sma(length=200, append=True)
df.ta.rsi(length=14, append=True)
df.ta.macd(fast=12, slow=26, signal=9, append=True)

# Option C: Manual with pure pandas/numpy
df['SMA_50'] = df['Close'].rolling(window=50).mean()
df['SMA_200'] = df['Close'].rolling(window=200).mean()

# Manual RSI
delta = df['Close'].diff()
gain = delta.where(delta > 0, 0).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['RSI'] = 100 - (100 / (1 + rs))

# Golden cross detection
df['golden_cross'] = (
    (df['SMA_50'] > df['SMA_200']) & 
    (df['SMA_50'].shift(1) <= df['SMA_200'].shift(1))
)
```

Manual calculation with pandas works perfectly for the five indicators needed here and eliminates all external dependencies. For a screener that processes hundreds of stocks, the performance difference versus TA-Lib is negligible since the bottleneck is data fetching, not computation.

---

## DCF estimation: a practical implementation

A simple DCF model projects future free cash flows, discounts them to present value, adds a terminal value, and compares the resulting intrinsic value to the current stock price. The implementation below uses yfinance data for both markets (Korean stocks via `.KS`/`.KQ` suffixes, US stocks directly).

```python
import yfinance as yf
import numpy as np

def simple_dcf(ticker_symbol, growth_rate=0.08, discount_rate=0.10,
               terminal_growth=0.025, projection_years=5):
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    cf = ticker.cashflow
    
    # Get most recent free cash flow
    try:
        operating_cf = cf.loc['Operating Cash Flow'].iloc[0]
        capex = cf.loc['Capital Expenditure'].iloc[0]
        current_fcf = operating_cf + capex  # capex is negative
    except:
        current_fcf = info.get('freeCashflow', 0)
    
    if not current_fcf or current_fcf <= 0:
        return None  # DCF not applicable for negative FCF
    
    shares = info.get('sharesOutstanding', 1)
    current_price = info.get('currentPrice', 0)
    net_debt = info.get('totalDebt', 0) - info.get('totalCash', 0)
    
    # Project and discount future FCFs
    pv_fcfs = sum(
        current_fcf * (1 + growth_rate)**yr / (1 + discount_rate)**yr
        for yr in range(1, projection_years + 1)
    )
    
    # Terminal value (Gordon Growth Model)
    terminal_fcf = current_fcf * (1 + growth_rate)**projection_years * (1 + terminal_growth)
    pv_terminal = (terminal_fcf / (discount_rate - terminal_growth)) / (1 + discount_rate)**projection_years
    
    # Intrinsic value per share
    equity_value = pv_fcfs + pv_terminal - net_debt
    intrinsic_value = equity_value / shares
    margin_of_safety = (intrinsic_value - current_price) / intrinsic_value * 100
    
    return {
        'intrinsic_value': round(intrinsic_value, 2),
        'current_price': current_price,
        'margin_of_safety_pct': round(margin_of_safety, 2),
        'dcf_undervalued': margin_of_safety > 20  # 20% margin threshold
    }
```

The critical assumptions are **growth rate** (typically 3–15%, based on historical FCF CAGR), **discount rate** (8–12%, approximating WACC), and **terminal growth** (2–3%, never exceeding long-term GDP growth). For Korean stocks, use the same model but be aware that KRW-denominated cash flows need no conversion—the intrinsic value will be in won. A simplified WACC can be estimated using CAPM: `cost_of_equity = risk_free_rate + beta × (market_return - risk_free_rate)`, where beta is available from `ticker.info['beta']`.

---

## The complete screening pipeline architecture

The most efficient architecture uses a **funnel approach**: bulk-filter cheap, then enrich expensive. This minimizes API calls and avoids rate limits.

**Stage 1 — Bulk fundamental filter (pykrx for KR, yfinance batch for US):** Pull PER and PBR for all stocks in a single bulk query. Eliminate stocks with PER > 15, PBR > 1.5, or negative earnings. This typically reduces thousands of candidates to 100–200.

**Stage 2 — Detailed fundamental enrichment:** For surviving candidates only, fetch ROE, EV/EBITDA, and FCF data from yfinance (with 0.5s delays). Apply filters: ROE > 15%, EV/EBITDA < 10. Run the DCF model and keep stocks with margin of safety > 20%.

**Stage 3 — Technical overlay:** Fetch 1-year OHLCV history for remaining candidates (typically 30–80 stocks). Calculate SMA-50, SMA-200, RSI-14, and MACD. Filter for: price above both moving averages, MACD histogram positive, RSI between 30 and 70.

**Stage 4 — Scoring and ranking:** Assign a composite score weighting each factor.

```python
import pandas as pd
import time

def composite_score(row):
    score = 0
    # Fundamental scores (lower = better for PER, PBR, EV/EBITDA)
    if row.get('PER') and 0 < row['PER'] < 10: score += 3
    elif row.get('PER') and 0 < row['PER'] < 15: score += 1
    if row.get('PBR') and 0 < row['PBR'] < 1.0: score += 3
    elif row.get('PBR') and 0 < row['PBR'] < 1.5: score += 1
    if row.get('ROE') and row['ROE'] > 0.20: score += 3
    elif row.get('ROE') and row['ROE'] > 0.15: score += 1
    if row.get('EV_EBITDA') and 0 < row['EV_EBITDA'] < 8: score += 3
    elif row.get('EV_EBITDA') and 0 < row['EV_EBITDA'] < 10: score += 1
    if row.get('dcf_undervalued'): score += 3
    
    # Technical scores
    if row.get('price_above_sma50'): score += 2
    if row.get('price_above_sma200'): score += 2
    if row.get('macd_positive'): score += 2
    if row.get('rsi_healthy'): score += 1  # 30 < RSI < 70
    if row.get('golden_cross_recent'): score += 2
    return score

# Apply scoring and rank
df['score'] = df.apply(composite_score, axis=1)
top_picks = df.nlargest(20, 'score')
```

For handling missing data, use `pd.to_numeric(errors='coerce')` liberally and skip stocks where critical metrics are unavailable rather than imputing. Cache all fetched data to a local SQLite database or parquet files using timestamps, so re-runs within the same day avoid refetching.

---

## Visualization: mplfinance for static, plotly for interactive

**mplfinance** (maintained under matplotlib/mplfinance) produces publication-quality candlestick charts with just a few lines. Its `addplot` parameter handles RSI and MACD subplots cleanly.

```python
import mplfinance as mpf

# Calculate indicators first, then plot
apds = [
    mpf.make_addplot(df['SMA_50'], color='blue', width=1),
    mpf.make_addplot(df['SMA_200'], color='red', width=1),
    mpf.make_addplot(df['RSI'], panel=2, color='purple', ylabel='RSI'),
    mpf.make_addplot(df['MACD'], panel=3, color='blue', ylabel='MACD'),
    mpf.make_addplot(df['MACD_signal'], panel=3, color='orange'),
    mpf.make_addplot(df['MACD_hist'], panel=3, type='bar', color='gray'),
]

mpf.plot(df, type='candle', style='yahoo', volume=True,
         addplot=apds, title='Stock Analysis',
         figsize=(14, 10), panel_ratios=(4, 1, 2, 2))
```

**Plotly** (`plotly.graph_objects`) creates interactive charts with zoom, hover details, and range sliders. It is the better choice for exploring screened candidates interactively. Use `go.Candlestick` for the price panel and `go.Scatter`/`go.Bar` for indicators in subplots created with `make_subplots(rows=3, cols=1, shared_xaxes=True)`.

For a dashboard view of all screened stocks, plotly's `Dash` framework or a simple grid of mplfinance `savefig()` outputs both work. The simpler approach is to generate a PDF report with one page per stock using matplotlib's `PdfPages` backend.

---

## Conclusion

The practical stack for a dual-market screener is **pykrx + yfinance + ta + mplfinance**, with FinanceDataReader and OpenDartReader as supplements for Korean financial statement data. The most important architectural decision is the funnel pattern: bulk-filter with pykrx's single-call market queries first, then use yfinance only for the narrowed candidate list. This keeps total API calls under a few hundred per screening run, well within free-tier limits.

Three things to watch going forward: yfinance's `curl_cffi` dependency continues to cause installation headaches on some platforms—pin to a tested version. The original pandas-ta may be archived by mid-2026; migrate to pandas-ta-classic if needed. And pykrx scrapes KRX/Naver HTML, meaning any website redesign can temporarily break data access—FinanceDataReader serves as a reliable backup source for the same underlying data.

The combination of Korean bulk APIs (where one call returns PER/PBR for 2,000+ stocks) with yfinance's rich per-stock fundamentals creates a screening system that no single library could provide alone. Starting with the funnel approach and composite scoring described above, a complete screener can be built in under 500 lines of Python.