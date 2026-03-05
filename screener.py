"""
stock.md 방법론 기반 한국/미국 주식 스크리너
Stage 1: 벌크 PER/PBR 필터
Stage 2: ROE, EV/EBITDA, DCF 심화 필터
Stage 3: 기술적 지표 필터 (SMA50/200, RSI, MACD)
Stage 4: 복합 점수 산정 및 랭킹
"""

import time
import warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

# ── 설정 ──────────────────────────────────────────
KR_TICKERS = [
    # 대형주 / 우량주 풀
    "005930.KS","000660.KS","035420.KS","005380.KS","051910.KS",
    "006400.KS","035720.KS","068270.KS","105560.KS","055550.KS",
    "316140.KS","015760.KS","017670.KS","033780.KS","010950.KS",
    "012330.KS","032830.KS","003670.KS","096770.KS","034730.KS",
    "207940.KS","000270.KS","028260.KS","066570.KS","323410.KS",
    "018260.KS","011200.KS","009150.KS","090430.KS","024110.KS",
    # 코스닥 대표주
    "247540.KQ","091990.KQ","086900.KQ","196170.KQ","041510.KQ",
    "293490.KQ","145020.KQ","039030.KQ","357780.KQ","112040.KQ",
]

US_TICKERS = [
    "AAPL","MSFT","GOOGL","META","AMZN","NVDA","BRK-B","JPM",
    "JNJ","UNH","V","MA","HD","PG","ABBV","MRK","CVX","XOM",
    "BAC","WMT","KO","PEP","TMO","ABT","COST","AVGO","CRM","ACN",
    "LLY","DHR","MCD","NKE","TXN","NEE","QCOM","HON","PM","RTX",
    "IBM","INTC","GE","CAT","DE","MMM","GS","MS","AXP","SPGI",
]

# ── 헬퍼 ──────────────────────────────────────────
def safe_get(d, key, default=None):
    v = d.get(key, default)
    return default if v is None or (isinstance(v, float) and np.isnan(v)) else v


def calc_technical(hist: pd.DataFrame) -> dict:
    """순수 pandas로 SMA50/200, RSI14, MACD 계산"""
    close = hist['Close'].squeeze()
    if len(close) < 200:
        return {}

    sma50  = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    price  = close.iloc[-1]

    # RSI
    delta = close.diff()
    gain  = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rsi   = (100 - 100 / (1 + gain / loss)).iloc[-1]

    # MACD
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist   = (macd_line - signal_line).iloc[-1]

    # 골든크로스 (최근 5일 내)
    cross = (
        (close.rolling(50).mean() > close.rolling(200).mean()) &
        (close.rolling(50).mean().shift(1) <= close.rolling(200).mean().shift(1))
    ).tail(5).any()

    return {
        'price':             round(float(price), 2),
        'sma50':             round(float(sma50), 2),
        'sma200':            round(float(sma200), 2),
        'rsi':               round(float(rsi), 1),
        'macd_hist':         round(float(macd_hist), 4),
        'price_above_sma50':  price > sma50,
        'price_above_sma200': price > sma200,
        'macd_positive':      macd_hist > 0,
        'rsi_healthy':        30 < rsi < 70,
        'golden_cross':       bool(cross),
    }


def simple_dcf(info: dict) -> dict:
    fcf = safe_get(info, 'freeCashflow', 0)
    if not fcf or fcf <= 0:
        return {}
    shares  = safe_get(info, 'sharesOutstanding', 1)
    price   = safe_get(info, 'currentPrice', 0)
    debt    = safe_get(info, 'totalDebt', 0)
    cash    = safe_get(info, 'totalCash', 0)
    g, r, tg, yrs = 0.08, 0.10, 0.025, 5

    pv = sum(fcf*(1+g)**y / (1+r)**y for y in range(1, yrs+1))
    tv = (fcf*(1+g)**yrs*(1+tg) / (r-tg)) / (1+r)**yrs
    iv = (pv + tv - (debt - cash)) / shares
    mos = (iv - price) / iv * 100 if iv > 0 else -999

    return {'intrinsic_value': round(iv, 2), 'mos_pct': round(mos, 1),
            'dcf_undervalued': mos > 20}


def composite_score(row: dict) -> int:
    s = 0
    per = row.get('per')
    pbr = row.get('pbr')
    roe = row.get('roe')
    ev  = row.get('ev_ebitda')

    if per and 0 < per < 10:  s += 3
    elif per and 0 < per < 15: s += 1
    if pbr and 0 < pbr < 1.0:  s += 3
    elif pbr and 0 < pbr < 1.5: s += 1
    if roe and roe > 0.20:  s += 3
    elif roe and roe > 0.15: s += 1
    if ev and 0 < ev < 8:   s += 3
    elif ev and 0 < ev < 10: s += 1
    if row.get('dcf_undervalued'): s += 3

    if row.get('price_above_sma50'):  s += 2
    if row.get('price_above_sma200'): s += 2
    if row.get('macd_positive'):      s += 2
    if row.get('rsi_healthy'):        s += 1
    if row.get('golden_cross'):       s += 2
    return s


# ── 메인 스크리닝 ──────────────────────────────────
def screen(tickers: list, label: str) -> list:
    print(f"\n{'='*50}")
    print(f"[{label}] {len(tickers)}개 종목 스크리닝 시작")
    print('='*50)

    results = []

    for i, sym in enumerate(tickers):
        try:
            t = yf.Ticker(sym)
            info = t.info

            name  = safe_get(info, 'longName') or safe_get(info, 'shortName', sym)
            per   = safe_get(info, 'trailingPE')
            pbr   = safe_get(info, 'priceToBook')
            roe   = safe_get(info, 'returnOnEquity')
            ev    = safe_get(info, 'enterpriseToEbitda')

            # Stage 1: PER/PBR 1차 필터
            if per is None or pbr is None:
                print(f"  [{i+1:2d}/{len(tickers)}] {sym:15s} - 데이터 없음 (skip)")
                time.sleep(0.3)
                continue
            if per <= 0 or per > 20 or pbr <= 0 or pbr > 2.0:
                print(f"  [{i+1:2d}/{len(tickers)}] {sym:15s} - PER={per:.1f} PBR={pbr:.2f} (필터 탈락)")
                time.sleep(0.3)
                continue

            # Stage 2: ROE / EV/EBITDA / DCF
            dcf = simple_dcf(info)

            # Stage 3: 기술적 지표
            hist = t.history(period='1y', interval='1d', auto_adjust=True)
            tech = calc_technical(hist)

            row = {
                'ticker': sym, 'name': name,
                'per': per, 'pbr': pbr, 'roe': roe, 'ev_ebitda': ev,
                **dcf, **tech,
            }
            row['score'] = composite_score(row)
            results.append(row)

            status = f"PER={per:.1f} PBR={pbr:.2f}"
            if roe:   status += f" ROE={roe*100:.1f}%"
            if ev:    status += f" EV/E={ev:.1f}"
            if tech:  status += f" RSI={tech.get('rsi','?')}"
            status += f" → 점수:{row['score']}"
            print(f"  [{i+1:2d}/{len(tickers)}] {sym:15s} {status}")

        except Exception as e:
            print(f"  [{i+1:2d}/{len(tickers)}] {sym:15s} - 오류: {e}")

        time.sleep(0.5)

    return results


# ── 실행 ──────────────────────────────────────────
if __name__ == '__main__':
    kr_results = screen(KR_TICKERS, "한국주식")
    us_results = screen(US_TICKERS, "미국주식")

    all_results = kr_results + us_results
    if not all_results:
        print("결과 없음")
        exit()

    df = pd.DataFrame(all_results).sort_values('score', ascending=False)

    print("\n" + "="*70)
    print("★ 최종 추천 종목 TOP 20 ★")
    print("="*70)

    cols = ['ticker','name','score','per','pbr','roe','ev_ebitda',
            'mos_pct','rsi','price_above_sma50','price_above_sma200',
            'macd_positive','golden_cross']
    top = df[[c for c in cols if c in df.columns]].head(20)

    for rank, (_, r) in enumerate(top.iterrows(), 1):
        roe_str = f"{r['roe']*100:.1f}%" if pd.notna(r.get('roe')) and r.get('roe') else "N/A"
        ev_str  = f"{r['ev_ebitda']:.1f}" if pd.notna(r.get('ev_ebitda')) and r.get('ev_ebitda') else "N/A"
        mos_str = f"{r['mos_pct']:.1f}%" if pd.notna(r.get('mos_pct')) and r.get('mos_pct') else "N/A"
        flags   = []
        if r.get('price_above_sma200'): flags.append("↑MA200")
        if r.get('macd_positive'):      flags.append("MACD+")
        if r.get('golden_cross'):       flags.append("골든크로스")
        if r.get('dcf_undervalued'):    flags.append("DCF저평가")

        print(f"  {rank:2d}위 [{r['score']:2d}점] {r['ticker']:15s} {str(r.get('name',''))[:20]:20s} "
              f"PER={r['per']:.1f} PBR={r['pbr']:.2f} ROE={roe_str} "
              f"EV/E={ev_str} DCF={mos_str}  {' '.join(flags)}")

    # CSV 저장
    df.to_csv('/home/dalbol/stock-analyzer/screener_result.csv', index=False, encoding='utf-8-sig')
    print(f"\n전체 결과 저장: screener_result.csv")
