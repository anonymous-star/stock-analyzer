import asyncio
from concurrent.futures import ThreadPoolExecutor
from services.stock_service import get_quote
from services.technical_service import get_technical_indicators

# 분석 대상 종목 풀
DEFAULT_TICKERS = [
    # === 나스닥 100 ===
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "AVGO",
    "TSLA", "COST", "NFLX", "AMD", "ADBE", "PEP", "QCOM", "TMUS",
    "CSCO", "INTC", "INTU", "CMCSA", "TXN", "AMGN", "HON", "AMAT",
    "BKNG", "ISRG", "LRCX", "VRTX", "ADI", "REGN", "KLAC", "PANW",
    "ADP", "MDLZ", "SNPS", "CDNS", "GILD", "MELI", "CRWD", "PYPL",
    "MAR", "CTAS", "ABNB", "MRVL", "ORLY", "FTNT", "CEG", "DASH",
    "WDAY", "CSX", "NXPI", "ADSK", "ROP", "FANG", "MNST", "PCAR",
    "ROST", "AEP", "PAYX", "FAST", "KDP", "DDOG", "ODFL", "KHC",
    "EA", "VRSK", "CPRT", "GEHC", "EXC", "LULU", "BKR", "XEL",
    "CTSH", "IDXX", "CCEP", "TTD", "MCHP", "ON", "CDW", "ANSS",
    "DXCM", "GFS", "ILMN", "WBD", "ZS", "MDB", "TEAM", "BIIB",
    "DLTR", "ARM", "SMCI", "APP", "PLTR", "COIN", "MSTR", "CRSP",
    # === 코스피 시가총액 상위 50 ===
    "005930.KS",  # 삼성전자
    "000660.KS",  # SK하이닉스
    "207940.KS",  # 삼성바이오로직스
    "373220.KS",  # LG에너지솔루션
    "005380.KS",  # 현대차
    "006400.KS",  # 삼성SDI
    "035420.KS",  # NAVER
    "000270.KS",  # 기아
    "068270.KS",  # 셀트리온
    "051910.KS",  # LG화학
    "105560.KS",  # KB금융
    "055550.KS",  # 신한지주
    "035720.KS",  # 카카오
    "005490.KS",  # POSCO홀딩스
    "028260.KS",  # 삼성물산
    "012330.KS",  # 현대모비스
    "066570.KS",  # LG전자
    "003670.KS",  # 포스코퓨처엠
    "032830.KS",  # 삼성생명
    "034730.KS",  # SK
    "017670.KS",  # SK텔레콤
    "000810.KS",  # 삼성화재
    "009150.KS",  # 삼성전기
    "003550.KS",  # LG
    "096770.KS",  # SK이노베이션
    "033780.KS",  # KT&G
    "011200.KS",  # HMM
    "010130.KS",  # 고려아연
    "086790.KS",  # 하나금융지주
    "316140.KS",  # 우리금융지주
    "010950.KS",  # S-Oil
    "030200.KS",  # KT
    "015760.KS",  # 한국전력
    "011170.KS",  # 롯데케미칼
    "034020.KS",  # 두산에너빌리티
    "018260.KS",  # 삼성에스디에스
    "024110.KS",  # 기업은행
    "036570.KS",  # 엔씨소프트
    "259960.KS",  # 크래프톤
    "352820.KS",  # 하이브
    "011790.KS",  # SKC
    "047050.KS",  # 포스코인터내셔널
    "090430.KS",  # 아모레퍼시픽
    "006800.KS",  # 미래에셋증권
    "000720.KS",  # 현대건설
    "004020.KS",  # 현대제철
    "010140.KS",  # 삼성중공업
    "042700.KS",  # 한미약품
    "326030.KS",  # SK바이오팜
    "003490.KS",  # 대한항공
]

_executor = ThreadPoolExecutor(max_workers=20)


def _score_technical(tech: dict) -> tuple[int, str, list[str]]:
    """
    기술적 지표 점수화.
    반환: (score -6~+6, recommendation, reasons)
    """
    score = 0
    reasons = []
    signals = tech.get("signals", {})
    price = tech.get("current_price")
    ma20 = tech.get("ma20")
    ma50 = tech.get("ma50")
    ma200 = tech.get("ma200")
    rsi = tech.get("rsi")
    macd = tech.get("macd") or {}
    bb = tech.get("bollinger_bands") or {}

    # MA 추세
    ma_trend = signals.get("ma_trend")
    if ma_trend == "bullish":
        score += 2
        reasons.append("이동평균선 정배열 (상승추세)")
    elif ma_trend == "bearish":
        score -= 2
        reasons.append("이동평균선 역배열 (하락추세)")

    # 장기 MA200 위
    if price and ma200:
        if price > ma200:
            score += 1
            reasons.append(f"MA200 상회 (장기 강세)")
        else:
            score -= 1

    # RSI
    rsi_signal = signals.get("rsi_signal")
    if rsi_signal == "oversold":
        score += 2
        reasons.append(f"RSI {rsi:.1f} — 과매도 반등 기대")
    elif rsi_signal == "overbought":
        score -= 1
        reasons.append(f"RSI {rsi:.1f} — 과매수 주의")

    # MACD
    macd_signal = signals.get("macd_signal")
    if macd_signal == "bullish":
        score += 1
        reasons.append("MACD 골든크로스")
    elif macd_signal == "bearish":
        score -= 1
        reasons.append("MACD 데드크로스")

    # 볼린저밴드
    bb_pos = signals.get("bb_position")
    if bb_pos == "below_lower":
        score += 2
        reasons.append("볼린저밴드 하단 — 단기 반등 가능")
    elif bb_pos == "above_upper":
        score -= 1
        reasons.append("볼린저밴드 상단 돌파 — 과열 주의")

    # 추천 결정
    if score >= 3:
        rec = "BUY"
    elif score <= -2:
        rec = "SELL"
    else:
        rec = "HOLD"

    return score, rec, reasons[:3]  # 이유는 최대 3개


def _analyze_single(ticker: str) -> dict | None:
    """단일 종목 분석 (스레드에서 실행)."""
    try:
        tech = get_technical_indicators(ticker)
        if "error" in tech:
            return None
        quote = get_quote(ticker)
        if not quote.get("current_price"):
            return None

        score, rec, reasons = _score_technical(tech)

        return {
            "ticker": ticker,
            "name": quote.get("name") or ticker,
            "current_price": quote.get("current_price"),
            "change_percent": quote.get("change_percent"),
            "currency": quote.get("currency"),
            "recommendation": rec,
            "score": score,
            "reasons": reasons,
            "rsi": tech.get("rsi"),
            "ma_trend": (tech.get("signals") or {}).get("ma_trend"),
        }
    except Exception:
        return None


async def get_recommendations(tickers: list[str] | None = None, limit: int = 20) -> list[dict]:
    """
    여러 종목을 병렬로 기술적 지표 분석해 추천 목록 반환 (점수 내림차순).
    """
    pool = tickers if tickers else DEFAULT_TICKERS
    loop = asyncio.get_event_loop()

    futures = [loop.run_in_executor(_executor, _analyze_single, t) for t in pool]
    raw_results = await asyncio.gather(*futures)

    results = [r for r in raw_results if r is not None]

    # BUY 우선, 점수 높은 순 정렬
    results.sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))
    return results[:limit]
