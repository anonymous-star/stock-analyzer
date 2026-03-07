import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from services.stock_service import get_quote
from services.technical_service import get_technical_indicators
from services.sentiment_service import score_headlines

# 캐시: {"data": [...], "timestamp": float}
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 3600  # 1시간

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

_executor = ThreadPoolExecutor(max_workers=5)


# ── 점수 체계 ──
# 기술적(-7~+8), 재무(-4~+6), 거래량(-3~+4), 모멘텀/반등(-0~+3), 뉴스(-3~+3)
# 합산 범위: -17 ~ +24
# BUY >= 5, SELL <= -5, 나머지 HOLD


def _score_technical(tech: dict, quote: dict) -> tuple[int, list[str]]:
    """
    기술적 지표 점수화 (52주 고저 포함).
    반환: (score -7~+7, reasons)
    """
    score = 0
    reasons = []
    signals = tech.get("signals", {})
    price = tech.get("current_price")
    ma200 = tech.get("ma200")
    rsi = tech.get("rsi")

    # MA 추세 (+2/-2)
    ma_trend = signals.get("ma_trend")
    if ma_trend == "bullish":
        score += 2
        reasons.append("이동평균선 정배열 (상승추세)")
    elif ma_trend == "bearish":
        score -= 2
        reasons.append("이동평균선 역배열 (하락추세)")

    # 장기 MA200 (+1/-1)
    if price and ma200:
        if price > ma200:
            score += 1
            reasons.append("MA200 상회 (장기 강세)")
        else:
            score -= 1

    # RSI (+2/-1)
    rsi_signal = signals.get("rsi_signal")
    if rsi_signal == "oversold":
        score += 2
        reasons.append(f"RSI {rsi:.1f} — 과매도 반등 기대")
    elif rsi_signal == "overbought":
        score -= 1
        reasons.append(f"RSI {rsi:.1f} — 과매수 주의")

    # MACD (+1/-1)
    macd_signal = signals.get("macd_signal")
    if macd_signal == "bullish":
        score += 1
        reasons.append("MACD 골든크로스")
    elif macd_signal == "bearish":
        score -= 1
        reasons.append("MACD 데드크로스")

    # 볼린저밴드 (+2/-1)
    bb_pos = signals.get("bb_position")
    if bb_pos == "below_lower":
        score += 2
        reasons.append("볼린저밴드 하단 — 단기 반등 가능")
    elif bb_pos == "above_upper":
        score -= 1
        reasons.append("볼린저밴드 상단 돌파 — 과열 주의")

    # 52주 고가/저가 근접도 (강화된 반등 보호)
    week52_high = quote.get("52_week_high")
    week52_low = quote.get("52_week_low")
    if price and week52_high and week52_low and week52_high > 0:
        pct_from_high = (price - week52_high) / week52_high
        pct_from_low = (price - week52_low) / week52_low if week52_low > 0 else 0

        if pct_from_high >= -0.05:  # 52주 고가 5% 이내
            score -= 1
            reasons.append("52주 고가 근접 — 상승 여력 제한")
        elif pct_from_low <= 0.10:  # 52주 저가 10% 이내
            score += 2
            reasons.append("52주 저가 근접 — 반등 가능성 높음")
        elif pct_from_low <= 0.30:  # 52주 저가 30% 이내
            score += 1
            reasons.append("52주 저가 근처 — 추가 하락 제한적")

    return score, reasons


def _score_financial(financials: dict) -> tuple[int, list[str]]:
    """
    재무 지표 점수화.
    반환: (score -4~+6, reasons)
    """
    score = 0
    reasons = []

    pe = financials.get("pe_ratio")
    pb = financials.get("pb_ratio")
    roe = financials.get("roe")
    de = financials.get("debt_to_equity")
    rev_growth = financials.get("revenue_growth")
    earn_growth = financials.get("earnings_growth")

    # PER 점수 (+2/-1)
    if pe is not None:
        if 0 < pe < 15:
            score += 2
            reasons.append(f"PER {pe:.1f} — 저평가")
        elif 0 < pe < 25:
            score += 1
        elif pe > 40:
            score -= 1
            reasons.append(f"PER {pe:.1f} — 고평가 주의")

    # PBR 점수 (+1/-1)
    if pb is not None:
        if 0 < pb < 1:
            score += 1
            reasons.append(f"PBR {pb:.2f} — 자산 대비 저평가")
        elif pb > 5:
            score -= 1

    # ROE 점수 (+1/-1)
    if roe is not None:
        if roe > 0.15:
            score += 1
            reasons.append(f"ROE {roe*100:.1f}% — 높은 수익성")
        elif roe < 0:
            score -= 1
            reasons.append(f"ROE 음수 — 수익성 악화")

    # 부채비율 (+0/-1)
    if de is not None:
        if de > 200:
            score -= 1
            reasons.append(f"부채비율 {de:.0f}% — 재무 위험")

    # 성장률 (+1/0)
    if rev_growth is not None and rev_growth > 0.10:
        score += 1
        reasons.append(f"매출 성장 {rev_growth*100:.1f}%")
    if earn_growth is not None and earn_growth > 0.15:
        score += 1

    # 클램핑: -4 ~ +6
    score = max(-4, min(6, score))
    return score, reasons


def _score_volume(tech: dict, change_percent: float | None) -> tuple[int, list[str]]:
    """
    거래량 분석 점수화.
    반환: (score -3~+4, reasons)
    """
    score = 0
    reasons = []

    current_vol = tech.get("current_volume")
    vol_ma20 = tech.get("volume_ma20")

    if current_vol and vol_ma20 and vol_ma20 > 0:
        vol_ratio = current_vol / vol_ma20
        change = change_percent or 0

        if vol_ratio > 2.0:
            # 거래량 2배 이상 급증
            if change > 0:
                score += 3
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x + 상승 — 강한 매수세")
            elif change < -2:
                score -= 2
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x + 하락 — 투매 위험")
            else:
                score += 1
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x — 관심 집중")
        elif vol_ratio > 1.5:
            if change > 0:
                score += 2
                reasons.append(f"거래량 증가 {vol_ratio:.1f}x — 매수세 확인")
            elif change < -2:
                score -= 1
        elif vol_ratio < 0.5:
            score -= 1
            reasons.append("거래량 급감 — 관심 저하")

        # 추세 확인: 상승 + 거래량 증가 조합 추가 보너스
        if change > 1 and vol_ratio > 1.3:
            score += 1

    # 클램핑: -3 ~ +4
    score = max(-3, min(4, score))
    return score, reasons


def _score_momentum(tech: dict, quote: dict) -> tuple[int, list[str]]:
    """
    모멘텀/평균회귀 점수 (SELL 신호 반등 보호).
    52주 저가 근처에서 이미 급락한 종목의 SELL 신호를 억제.
    반환: (score 0~+3, reasons)
    """
    score = 0
    reasons = []

    mom5 = tech.get("momentum_5d")
    mom10 = tech.get("momentum_10d")
    down_streak = tech.get("down_streak", 0)
    price = tech.get("current_price")
    week52_low = quote.get("52_week_low")

    # 52주 저가 대비 위치
    near_low = False
    if price and week52_low and week52_low > 0:
        pct_from_low = (price - week52_low) / week52_low
        near_low = pct_from_low < 0.30

    # 이미 급락한 상태 (5일 모멘텀 < -5%) → 반등 가능
    if mom5 is not None and mom5 < -5 and near_low:
        score += 1
        reasons.append(f"5일 {mom5:+.1f}% 급락 후 반등 가능")

    # 깊은 하락 (10일 모멘텀 < -10%) → 강한 반등 기대
    if mom10 is not None and mom10 < -10 and near_low:
        score += 1
        reasons.append(f"10일 {mom10:+.1f}% 깊은 하락 — 기술적 반등 기대")

    # 3일+ 연속 하락 → 반등 임박
    if down_streak >= 3 and near_low:
        score += 1
        reasons.append(f"{down_streak}일 연속 하락 — 반등 임박")

    # 클램핑: 0 ~ +3
    score = max(0, min(3, score))
    return score, reasons


def _score_news(headlines: list[str]) -> tuple[int, list[str]]:
    """
    뉴스 감성 점수.
    반환: (score -3~+3, reasons)
    """
    news_score, summary = score_headlines(headlines)
    reasons = [summary] if news_score != 0 else []
    return news_score, reasons


def _calc_confidence(total_score: int, breakdown: dict, tech: dict | None = None) -> int:
    """
    백테스트 데이터 기반 추천 확신도 계산 (%).

    기본 확신도 = 점수 크기 기반 (백테스트 교정)
    + 카테고리 합의 보너스
    + 품질 조정 (10년 백테스트 교정)

    10년 백테스트 품질 조정 근거 (매우 강력 BUY 93건 분석):
      - 변동성 >4%: 적중률 ~45% → 대폭 감점 (기존 5% → 4%로 강화)
      - 변동성 2-3%: 적중률 75%+ → 최적 구간 보너스
      - BB폭 >15%: 적중률 40% → 과도한 변동성 시그널, 감점
      - BB폭 8-15%: 적중률 73.6% → 보너스
      - RSI 변화 0~5: 적중률 82.4% → 안정적 회복 보너스
      - RSI 변화 >5: 적중률 59% → 급반등 후 되돌림 위험
      - MA20 기울기 0~0.5%: 적중률 43.8% → 약한 상승 함정 감점
      - MA20 기울기 >1%: 적중률 74%+ → 확실한 추세 보너스
      - MACD 가속도 >=0.1: 적중률 72-74% → 추세 개선 확인
      - 하락 연속 3일+: 실패 확률 높음 → 감점
    """
    abs_score = abs(total_score)

    if total_score >= 5:
        # BUY 확신도 (백테스트 교정)
        if abs_score >= 12:
            base = 85
        elif abs_score >= 10:
            base = 80
        elif abs_score >= 8:
            base = 76
        elif abs_score >= 6:
            base = 72
        elif abs_score >= 5:
            base = 60
        else:
            base = 55
    elif total_score <= -5:
        # SELL 확신도
        if abs_score >= 10:
            base = 80
        elif abs_score >= 8:
            base = 75
        elif abs_score >= 6:
            base = 70
        elif abs_score >= 5:
            base = 65
        else:
            base = 60
    else:
        # HOLD
        if abs_score <= 1:
            base = 65
        elif abs_score <= 2:
            base = 55
        else:
            base = 45

    # 카테고리 합의 보너스
    t = breakdown.get("technical", 0)
    f = breakdown.get("financial", 0)
    v = breakdown.get("volume", 0)

    if total_score > 0:
        agreeing = sum(1 for s in [t, f, v] if s > 0)
    elif total_score < 0:
        agreeing = sum(1 for s in [t, f, v] if s < 0)
    else:
        agreeing = 0

    if agreeing >= 3:
        base += 5
    elif agreeing >= 2:
        base += 2

    # 품질 조정 (tech 데이터가 있을 때만, 10년 백테스트 교정)
    if tech:
        volatility = tech.get("volatility")
        mom5 = tech.get("momentum_5d")
        macd_accel = tech.get("macd_accel")
        down_streak = tech.get("down_streak", 0)
        bb_width = tech.get("bb_width")
        rsi_change = tech.get("rsi_change_5d")
        ma20_slope = tech.get("ma20_slope")
        trend_20d = tech.get("trend_20d")

        if total_score >= 5:  # BUY 품질 조정
            # 변동성 (임계값 4%로 강화, 10년 데이터 기반)
            if volatility is not None:
                if volatility > 4:
                    base -= 12  # >4% 적중률 ~45% → 강력 감점
                elif 2 <= volatility <= 3:
                    base += 3   # 2-3% 최적 구간 (64.1%)
                elif volatility <= 4:
                    base += 1   # 3-4% 양호

            # BB 폭 (10년 160건 분석, 임계값 강화 15→12%)
            if bb_width is not None:
                if bb_width > 12:
                    base -= 8   # >12% 적중률 44.9% → 과도한 변동
                elif 8 <= bb_width <= 12:
                    base += 2   # 8-12% 적중률 64.7%

            # RSI 변화 (10년 분석)
            if rsi_change is not None:
                if rsi_change < -5:
                    base -= 6   # 적중률 37.5% → RSI 급락 중 진입은 위험
                elif 0 <= rsi_change <= 5:
                    base += 3   # 적중률 66.7% → 안정적 회복
                elif rsi_change > 5:
                    base -= 3   # 적중률 52.9-58% → 급반등 되돌림 위험

            # MA20 기울기 (약한 상승 함정 감지)
            if ma20_slope is not None:
                if 0 < ma20_slope <= 0.5:
                    base -= 6   # 적중률 43.8% → 약한 상승 함정
                elif ma20_slope > 1:
                    base += 2   # 적중률 57%+ → 확실한 추세

            # 5일 모멘텀 (0-3% 함정 구간 감지, 10년 160건 분석)
            if mom5 is not None:
                if 0 <= mom5 < 3:
                    base -= 5   # 적중률 44.4% → 약한 상승 함정
                elif mom5 >= 3:
                    base += 3   # 적중률 61% → 확실한 상승
                elif mom5 < -5:
                    base -= 6   # 적중률 낮음

            # 20일 추세 (10년 160건 분석)
            if trend_20d is not None:
                if 5 <= trend_20d <= 10:
                    base -= 6   # 적중률 47.9% → 미지근한 상승 함정
                elif -5 <= trend_20d < 0:
                    base += 4   # 적중률 86.7% → 조정 후 반등

            # MACD 가속도
            if macd_accel is not None:
                if macd_accel >= 0.5:
                    base += 3   # 적중률 69.6% → 강한 추세 개선
                elif macd_accel >= 0.1:
                    base += 1   # 적중률 55.9%
                elif macd_accel < -0.5:
                    base -= 4   # 추세 악화

            # 하락 연속일
            if down_streak >= 3:
                base -= 5   # 반등 기대보다 추가 하락 위험
            elif down_streak >= 2:
                base -= 3

            # 계절성 (7-9월 약세, 10년 분석)
            import datetime
            try:
                month = datetime.date.today().month
                if 7 <= month <= 9:
                    base -= 4   # 적중률 35.7% → 여름 약세
                elif month in (4, 5, 6, 10, 11, 12):
                    base += 2   # 적중률 68-70%
            except Exception:
                pass

        elif total_score <= -5:  # SELL 품질 조정
            if volatility is not None and volatility > 5:
                base -= 5   # 고변동성에서 SELL도 불확실
            if macd_accel is not None and macd_accel < 0:
                base += 3   # 추세 악화 확인 → SELL 확신 증가

    return min(95, max(30, base))


def _analyze_single(ticker: str, include_news: bool = False) -> dict | None:
    """단일 종목 분석 (스레드에서 실행)."""
    import time as _time
    for attempt in range(2):
        try:
            tech = get_technical_indicators(ticker)
            if "error" in tech:
                return None
            quote = get_quote(ticker)
            if not quote.get("current_price"):
                if attempt == 0:
                    _time.sleep(1)
                    continue
                return None

            # 1. 기술적 점수 (-7 ~ +8)
            tech_score, tech_reasons = _score_technical(tech, quote)

            # 2. 재무 점수 (-4 ~ +6)
            financials = quote.get("financials", {})
            fin_score, fin_reasons = _score_financial(financials)

            # 3. 거래량 점수 (-3 ~ +4)
            vol_score, vol_reasons = _score_volume(tech, quote.get("change_percent"))

            # 4. 모멘텀/반등 보호 (0 ~ +3)
            mom_score, mom_reasons = _score_momentum(tech, quote)

            # 5. 뉴스 점수 (-3 ~ +3) — 기본 스캔에서는 제외 (속도)
            news_score = 0
            news_reasons = []
            if include_news:
                try:
                    from services.news_service import get_news_headlines
                    headlines = get_news_headlines(ticker, limit=5)
                    news_score, news_reasons = _score_news(headlines)
                except Exception:
                    pass

            # 합산 (-17 ~ +24)
            total_score = tech_score + fin_score + vol_score + mom_score + news_score

            # 추천 결정
            if total_score >= 5:
                rec = "BUY"
            elif total_score <= -5:
                rec = "SELL"
            else:
                rec = "HOLD"

            # 모든 이유 합치기 (최대 5개)
            all_reasons = tech_reasons + fin_reasons + vol_reasons + mom_reasons + news_reasons

            # 거래량 비율 계산
            vol_ratio = None
            current_vol = tech.get("current_volume")
            vol_ma20 = tech.get("volume_ma20")
            if current_vol and vol_ma20 and vol_ma20 > 0:
                vol_ratio = round(current_vol / vol_ma20, 2)

            breakdown = {
                "technical": tech_score,
                "financial": fin_score,
                "volume": vol_score,
                "momentum": mom_score,
                "news": news_score,
            }

            confidence = _calc_confidence(total_score, breakdown, tech)

            return {
                "ticker": ticker,
                "name": quote.get("name") or ticker,
                "current_price": quote.get("current_price"),
                "change_percent": quote.get("change_percent"),
                "currency": quote.get("currency"),
                "recommendation": rec,
                "score": total_score,
                "max_score": 24,
                "confidence": confidence,
                "score_breakdown": breakdown,
                "reasons": all_reasons[:5],
                "rsi": tech.get("rsi"),
                "ma_trend": (tech.get("signals") or {}).get("ma_trend"),
                "pe_ratio": financials.get("pe_ratio"),
                "volume_ratio": vol_ratio,
            }
        except Exception:
            if attempt == 0:
                _time.sleep(1)
                continue
            return None
    return None


async def get_recommendations(tickers: list[str] | None = None, limit: int = 20) -> list[dict]:
    """
    여러 종목을 병렬로 복합 지표 분석해 추천 목록 반환 (점수 내림차순).
    기본 스캔: 뉴스 제외 (속도), 재무+거래량 포함.
    결과는 1시간 캐시.
    """
    # 커스텀 티커가 아니면 캐시 확인
    use_cache = tickers is None
    if use_cache and _cache["data"] is not None and (time.time() - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"][:limit]

    pool = tickers if tickers else DEFAULT_TICKERS
    # 기본 풀 스캔에서는 뉴스 제외, 소수 커스텀 티커일 때만 포함
    include_news = tickers is not None and len(tickers) <= 10
    loop = asyncio.get_event_loop()

    futures = [loop.run_in_executor(_executor, _analyze_single, t, include_news) for t in pool]
    raw_results = await asyncio.gather(*futures)

    results = [r for r in raw_results if r is not None]

    # BUY 우선, 점수 높은 순 정렬
    results.sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))

    if use_cache and results:
        _cache["data"] = results
        _cache["timestamp"] = time.time()

    return results[:limit]
