"""
한국 주식 스크리너 - pykrx 기반
stock.md 방법론: Stage1 pykrx 벌크 필터 → Stage2/3 yfinance 심화
"""
import time, warnings
import numpy as np
import pandas as pd
import yfinance as yf
from pykrx import stock as krx

warnings.filterwarnings('ignore')

TODAY = "20260228"  # 오늘 날짜

def calc_technical(hist):
    close = hist['Close'].squeeze()
    if len(close) < 200:
        return {}
    sma50  = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1]
    price  = close.iloc[-1]
    delta  = close.diff()
    gain   = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss   = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rsi    = (100 - 100 / (1 + gain / loss)).iloc[-1]
    ema12  = close.ewm(span=12).mean()
    ema26  = close.ewm(span=26).mean()
    hist_macd = ((ema12 - ema26) - (ema12 - ema26).ewm(span=9).mean()).iloc[-1]
    cross  = ((close.rolling(50).mean() > close.rolling(200).mean()) &
              (close.rolling(50).mean().shift(1) <= close.rolling(200).mean().shift(1))).tail(5).any()
    return {
        'price': round(float(price), 0),
        'rsi':   round(float(rsi), 1),
        'price_above_sma50':  price > sma50,
        'price_above_sma200': price > sma200,
        'macd_positive':      hist_macd > 0,
        'rsi_healthy':        30 < rsi < 70,
        'golden_cross':       bool(cross),
    }

def composite_score(row):
    s = 0
    per, pbr, roe, ev = row.get('per'), row.get('pbr'), row.get('roe'), row.get('ev_ebitda')
    if per and 0 < per < 10:  s += 3
    elif per and 0 < per < 15: s += 1
    if pbr and 0 < pbr < 1.0:  s += 3
    elif pbr and 0 < pbr < 1.5: s += 1
    if roe and roe > 0.20:  s += 3
    elif roe and roe > 0.15: s += 1
    if ev and 0 < ev < 8:   s += 3
    elif ev and 0 < ev < 10: s += 1
    if row.get('price_above_sma50'):  s += 2
    if row.get('price_above_sma200'): s += 2
    if row.get('macd_positive'):      s += 2
    if row.get('rsi_healthy'):        s += 1
    if row.get('golden_cross'):       s += 2
    return s

# ── Stage 1: pykrx 전체 시장 벌크 조회 ──
print("pykrx 전체 시장 PER/PBR 조회 중...")
try:
    fund = krx.get_market_fundamental(TODAY, market="ALL")
    print(f"  총 {len(fund)}개 종목 조회 완료")
    # PER 5~15, PBR 0.3~1.5 필터
    filtered = fund[(fund['PER'] > 5) & (fund['PER'] < 15) &
                    (fund['PBR'] > 0.3) & (fund['PBR'] < 1.5) &
                    (fund['EPS'] > 0)]
    print(f"  1차 필터(PER<15, PBR<1.5) 통과: {len(filtered)}개")
except Exception as e:
    print(f"  pykrx 오류: {e}")
    filtered = pd.DataFrame()

if len(filtered) == 0:
    print("데이터 없음. 종료.")
    exit()

# 시가총액 데이터 추가해서 대형주 우선 정렬
try:
    cap = krx.get_market_cap(TODAY, market="ALL")['시가총액']
    filtered = filtered.join(cap, how='left')
    filtered = filtered.sort_values('시가총액', ascending=False)
    print(f"  시가총액 기준 정렬 완료")
except:
    pass

# 종목명 가져오기
try:
    names = {t: krx.get_market_ticker_name(t) for t in filtered.index[:100]}
except:
    names = {}

# ── Stage 2/3: 상위 100개만 yfinance 심화 분석 ──
candidates = filtered.head(100)
print(f"\n상위 {len(candidates)}개 yfinance 심화 분석 시작...")

results = []
for i, (ticker, row) in enumerate(candidates.iterrows()):
    name   = names.get(ticker, ticker)
    per    = row.get('PER')
    pbr    = row.get('PBR')
    suffix = ".KS"  # pykrx는 KOSPI/KOSDAQ 구분 없이 섞여 있음

    # yfinance로 ROE, EV/EBITDA 조회
    roe, ev = None, None
    tech = {}
    for sfx in [".KS", ".KQ"]:
        try:
            yf_sym = ticker + sfx
            t = yf.Ticker(yf_sym)
            info = t.info
            if info.get('regularMarketPrice') or info.get('currentPrice'):
                roe = info.get('returnOnEquity')
                ev  = info.get('enterpriseToEbitda')
                hist = t.history(period='1y', interval='1d', auto_adjust=True)
                if len(hist) >= 50:
                    tech = calc_technical(hist)
                suffix = sfx
                break
        except:
            pass
        time.sleep(0.2)

    rec = {
        'ticker': ticker + suffix, 'name': name,
        'per': per, 'pbr': pbr, 'roe': roe, 'ev_ebitda': ev,
        **tech,
    }
    rec['score'] = composite_score(rec)
    results.append(rec)

    roe_str = f"{roe*100:.1f}%" if roe else "N/A"
    ev_str  = f"{ev:.1f}" if ev else "N/A"
    print(f"  [{i+1:3d}/{len(candidates)}] {ticker} {name[:12]:12s}  "
          f"PER={per:.1f} PBR={pbr:.2f} ROE={roe_str} EV/E={ev_str} → {rec['score']}점")
    time.sleep(0.3)

# ── 결과 출력 ──
df = pd.DataFrame(results).sort_values('score', ascending=False)
df.to_csv('/home/dalbol/stock-analyzer/screener_kr_result.csv', index=False, encoding='utf-8-sig')

print("\n" + "="*70)
print("★ 한국 주식 추천 TOP 15 ★")
print("="*70)
for rank, (_, r) in enumerate(df.head(15).iterrows(), 1):
    roe_str = f"{r['roe']*100:.1f}%" if r.get('roe') else "N/A"
    ev_str  = f"{r['ev_ebitda']:.1f}" if r.get('ev_ebitda') else "N/A"
    flags   = []
    if r.get('price_above_sma200'): flags.append("↑MA200")
    if r.get('macd_positive'):      flags.append("MACD+")
    if r.get('rsi_healthy'):        flags.append(f"RSI:{r.get('rsi','?')}")
    if r.get('golden_cross'):       flags.append("골든크로스")
    print(f"  {rank:2d}위 [{r['score']:2d}점] {r['ticker']:12s} {r['name'][:14]:14s} "
          f"PER={r['per']:.1f} PBR={r['pbr']:.2f} ROE={roe_str} EV/E={ev_str}  {' '.join(flags)}")
