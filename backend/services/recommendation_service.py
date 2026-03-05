from services.stock_service import get_quote
from services.technical_service import get_technical_indicators

# 분석 대상 종목 풀
DEFAULT_TICKERS = [
    # 미국
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "V", "UNH", "XOM", "LLY", "JNJ", "PG",
    # 한국
    "005930.KS", "000660.KS", "035420.KS", "005380.KS", "035720.KQ",
    "068270.KS", "207940.KS", "006400.KS", "051910.KS", "323410.KS",
]


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


def get_recommendations(tickers: list[str] | None = None, limit: int = 10) -> list[dict]:
    """
    여러 종목을 기술적 지표로 분석해 추천 목록 반환 (점수 내림차순).
    """
    pool = tickers if tickers else DEFAULT_TICKERS
    results = []

    for ticker in pool:
        try:
            tech = get_technical_indicators(ticker)
            if "error" in tech:
                continue
            quote = get_quote(ticker)
            if not quote.get("current_price"):
                continue

            score, rec, reasons = _score_technical(tech)

            results.append({
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
            })
        except Exception:
            continue

    # BUY 우선, 점수 높은 순 정렬
    results.sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))
    return results[:limit]
