"""
최종 한국/미국 주식 스크리너
- 한국: forwardPE + ROE + EV/EBITDA + DCF + 기술적 지표
- 미국: trailingPE/forwardPE + ROE + EV/EBITDA + DCF + 기술적 지표
"""
import time, warnings
import numpy as np
import pandas as pd
import yfinance as yf

warnings.filterwarnings('ignore')

# ── 한국 주요 종목 풀 ──
KR = [
    ("005930.KS","삼성전자"), ("000660.KS","SK하이닉스"), ("005380.KS","현대차"),
    ("051910.KS","LG화학"), ("006400.KS","삼성SDI"), ("035420.KS","NAVER"),
    ("035720.KS","카카오"), ("068270.KS","셀트리온"), ("105560.KS","KB금융"),
    ("055550.KS","신한지주"), ("316140.KS","우리금융"), ("015760.KS","한국전력"),
    ("017670.KS","SK텔레콤"), ("033780.KS","KT&G"), ("010950.KS","S-Oil"),
    ("012330.KS","현대모비스"), ("003670.KS","포스코퓨처엠"), ("096770.KS","SK이노베이션"),
    ("034730.KS","SK"), ("207940.KS","삼성바이오로직스"), ("000270.KS","기아"),
    ("028260.KS","삼성물산"), ("066570.KS","LG전자"), ("009150.KS","삼성전기"),
    ("024110.KS","기업은행"), ("018260.KS","삼성에스디에스"), ("011200.KS","HMM"),
    ("090430.KS","아모레퍼시픽"), ("032830.KS","삼성생명"), ("003490.KS","대한항공"),
    ("005490.KS","POSCO홀딩스"), ("000810.KS","삼성화재"), ("086790.KS","하나금융지주"),
    ("139480.KS","이마트"), ("271560.KS","오리온"), ("036570.KS","엔씨소프트"),
    ("041510.KQ","에스엠"), ("247540.KQ","에코프로비엠"), ("091990.KQ","셀트리온헬스케어"),
    ("196170.KQ","알테오젠"), ("357780.KQ","솔브레인"), ("086900.KQ","메디톡스"),
]

# ── 미국 주요 종목 풀 ──
US = [
    "BRK-B","JPM","BAC","C","WFC","GS","MS","BLK","AXP","SCHW",
    "INTC","IBM","CSCO","HPQ","DELL","WDC","STX","MU",
    "CVX","XOM","COP","PSX","VLO","EOG","OXY","MPC","SLB","HAL",
    "MRK","PFE","BMY","AMGN","GILD","BIIB","ABBV","CVS","CI","HUM",
    "T","VZ","CMCSA","PARA","WBD","FOX","IPG","OMC",
    "WMT","TGT","KR","CVS","HD","LOW","NKE","PVH",
    "F","GM","STLA","LUV","AAL","UAL","DAL",
]

def get_per(info):
    """trailingPE 없으면 forwardPE 사용"""
    return info.get('trailingPE') or info.get('forwardPE')

def get_pbr(info):
    """priceToBook 없으면 price/bookValue 계산"""
    pbr = info.get('priceToBook')
    if pbr:
        return pbr
    bv = info.get('bookValue')
    cp = info.get('currentPrice') or info.get('regularMarketPrice')
    if bv and bv > 0 and cp:
        return cp / bv
    return None

def simple_dcf(info):
    fcf = info.get('freeCashflow', 0)
    if not fcf or fcf <= 0:
        return {}
    shares = info.get('sharesOutstanding', 1) or 1
    price  = info.get('currentPrice') or info.get('regularMarketPrice', 0)
    debt   = info.get('totalDebt', 0) or 0
    cash   = info.get('totalCash', 0) or 0
    g, r, tg = 0.07, 0.10, 0.025
    pv  = sum(fcf*(1+g)**y / (1+r)**y for y in range(1, 6))
    tv  = (fcf*(1+g)**5*(1+tg) / (r-tg)) / (1+r)**5
    iv  = (pv + tv - (debt - cash)) / shares
    mos = (iv - price) / iv * 100 if iv > 0 and price > 0 else None
    return {'intrinsic_value': round(iv, 2), 'mos_pct': round(mos, 1) if mos else None,
            'dcf_undervalued': (mos or 0) > 20}

def calc_technical(hist):
    close = hist['Close'].squeeze()
    if len(close) < 60:
        return {}
    sma50  = close.rolling(50).mean().iloc[-1]
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    price  = close.iloc[-1]
    delta  = close.diff()
    gain   = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss   = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rsi    = (100 - 100 / (1 + gain / loss)).iloc[-1]
    ema12  = close.ewm(span=12).mean()
    ema26  = close.ewm(span=26).mean()
    macd_h = ((ema12-ema26) - (ema12-ema26).ewm(span=9).mean()).iloc[-1]
    cross  = False
    if sma200 is not None:
        s50 = close.rolling(50).mean()
        s200 = close.rolling(200).mean()
        cross = bool(((s50 > s200) & (s50.shift(1) <= s200.shift(1))).tail(5).any())
    return {
        'price': round(float(price), 2),
        'rsi':   round(float(rsi), 1),
        'price_above_sma50':  float(price) > float(sma50),
        'price_above_sma200': (float(price) > float(sma200)) if sma200 else False,
        'macd_positive':      float(macd_h) > 0,
        'rsi_healthy':        30 < float(rsi) < 70,
        'golden_cross':       cross,
    }

def composite_score(row):
    s = 0
    per, pbr = row.get('per'), row.get('pbr')
    roe, ev  = row.get('roe'), row.get('ev_ebitda')
    if per and 0 < per < 10:   s += 3
    elif per and 0 < per < 15: s += 2
    elif per and 0 < per < 20: s += 1
    if pbr and 0 < pbr < 1.0:  s += 3
    elif pbr and 0 < pbr < 1.5: s += 2
    elif pbr and 0 < pbr < 2.0: s += 1
    if roe and roe > 0.20:  s += 3
    elif roe and roe > 0.15: s += 2
    elif roe and roe > 0.10: s += 1
    if ev and 0 < ev < 8:    s += 3
    elif ev and 0 < ev < 12: s += 1
    if row.get('dcf_undervalued'): s += 3
    if row.get('price_above_sma50'):  s += 1
    if row.get('price_above_sma200'): s += 2
    if row.get('macd_positive'):      s += 2
    if row.get('rsi_healthy'):        s += 1
    if row.get('golden_cross'):       s += 2
    return s

def screen_tickers(tickers, label):
    print(f"\n{'='*55}\n[{label}] {len(tickers)}개 스크리닝\n{'='*55}")
    results = []
    for i, item in enumerate(tickers):
        sym  = item[0] if isinstance(item, tuple) else item
        name = item[1] if isinstance(item, tuple) else sym
        try:
            t    = yf.Ticker(sym)
            info = t.info
            per  = get_per(info)
            pbr  = get_pbr(info)
            roe  = info.get('returnOnEquity')
            ev   = info.get('enterpriseToEbitda')
            cp   = info.get('currentPrice') or info.get('regularMarketPrice')

            if not cp:
                print(f"  {sym:15s} - 시세 없음")
                time.sleep(0.3)
                continue

            dcf  = simple_dcf(info)
            hist = t.history(period='1y', interval='1d', auto_adjust=True)
            tech = calc_technical(hist)

            row = {'ticker': sym, 'name': name,
                   'per': per, 'pbr': pbr, 'roe': roe, 'ev_ebitda': ev, **dcf, **tech}
            row['score'] = composite_score(row)
            results.append(row)

            per_s = f"{per:.1f}" if per else "N/A"
            pbr_s = f"{pbr:.2f}" if pbr else "N/A"
            roe_s = f"{roe*100:.1f}%" if roe else "N/A"
            ev_s  = f"{ev:.1f}" if ev else "N/A"
            print(f"  [{i+1:2d}] {sym:15s} {name[:10]:10s}  "
                  f"PER={per_s:6s} PBR={pbr_s:5s} ROE={roe_s:7s} EV/E={ev_s:5s} → {row['score']}점")
        except Exception as e:
            print(f"  {sym:15s} - 오류: {str(e)[:40]}")
        time.sleep(0.4)
    return results

# ── 실행 ──
kr_res = screen_tickers(KR, "한국 주식")
us_res = screen_tickers(US, "미국 주식")

all_res = kr_res + us_res
if not all_res:
    print("결과 없음"); exit()

df = pd.DataFrame(all_res).sort_values('score', ascending=False)
df.to_csv('/home/dalbol/stock-analyzer/screener_final_result.csv', index=False, encoding='utf-8-sig')

# ── 최종 출력 ──
print("\n\n" + "★"*35)
print("     최종 추천 종목 TOP 20")
print("★"*35)
kr_top = df[df['ticker'].str.contains(r'\.(KS|KQ)')].head(10)
us_top = df[~df['ticker'].str.contains(r'\.(KS|KQ)')].head(10)

for label, sub in [("🇰🇷 한국 TOP 10", kr_top), ("🇺🇸 미국 TOP 10", us_top)]:
    print(f"\n【{label}】")
    print(f"  {'순위':>2}  {'점수':>3}  {'티커':12}  {'종목명':14}  {'PER':>6}  {'PBR':>5}  {'ROE':>7}  {'EV/E':>5}  {'DCF':>7}  신호")
    print("  " + "-"*85)
    for rank, (_, r) in enumerate(sub.iterrows(), 1):
        per_s = f"{r['per']:.1f}" if r.get('per') else "-"
        pbr_s = f"{r['pbr']:.2f}" if r.get('pbr') else "-"
        roe_s = f"{r['roe']*100:.1f}%" if r.get('roe') else "-"
        ev_s  = f"{r['ev_ebitda']:.1f}" if r.get('ev_ebitda') else "-"
        mos_s = f"{r['mos_pct']:.0f}%" if r.get('mos_pct') else "-"
        flags = []
        if r.get('price_above_sma200'): flags.append("MA200↑")
        if r.get('macd_positive'):      flags.append("MACD+")
        if r.get('rsi_healthy'):        flags.append(f"RSI:{r.get('rsi','?')}")
        if r.get('golden_cross'):       flags.append("골든크로스")
        if r.get('dcf_undervalued'):    flags.append("DCF저평가")
        print(f"  {rank:2d}위  {int(r['score']):3d}  {r['ticker']:12}  {r['name'][:13]:13s}  "
              f"{per_s:>6}  {pbr_s:>5}  {roe_s:>7}  {ev_s:>5}  {mos_s:>7}  {' '.join(flags)}")

print(f"\n전체 결과: screener_final_result.csv")
