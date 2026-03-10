import asyncio
import math
import time
from concurrent.futures import ThreadPoolExecutor
from services.stock_service import get_quote
from services.technical_service import get_technical_indicators
from services.sentiment_service import score_headlines
from services.ml_service import predict_confidence as ml_predict
from services.cache_service import get_cached_result, set_cached_result

# 캐시: {"data": [...], "timestamp": float}
_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 1 * 3600  # 1시간
_DISK_CACHE_KEY = "recommendations"

# 분석 진행률 추적
_progress = {"total": 0, "done": 0, "success": 0, "failed": 0, "running": False, "failed_tickers": []}
_analysis_lock = asyncio.Lock()

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
    "012450.KS",  # 한화에어로스페이스
    "042660.KS",  # 한화오션
    "329180.KS",  # HD현대중공업
    "009540.KS",  # HD한국조선해양
    "402340.KS",  # SK스퀘어
    "323410.KS",  # 카카오뱅크
    "267250.KS",  # HD현대
    "009830.KS",  # 한화솔루션
    "097950.KS",  # CJ제일제당
    "051900.KS",  # LG생활건강
    "138040.KS",  # 메리츠금융지주
    "005830.KS",  # DB손해보험
    "028300.KS",  # HLB
    "078930.KS",  # GS
    "251270.KS",  # 넷마블
    "020560.KS",  # 아시아나항공
    "028050.KS",  # 삼성엔지니어링
    "161390.KS",  # 한국타이어앤테크놀로지
    "008930.KS",  # 한미사이언스
    "247540.KS",  # 에코프로비엠
    "018880.KS",  # 한온시스템
    "029780.KS",  # 삼성카드
    # === 코스닥 주요 종목 ===
    "086520.KQ",  # 에코프로
    "196170.KQ",  # 알테오젠
    "066970.KQ",  # 엘앤에프
    "067630.KQ",  # HLB생명과학
    "277810.KQ",  # 레인보우로보틱스
    "068760.KQ",  # 셀트리온제약
    "058470.KQ",  # 리노공업
    "263750.KQ",  # 펄어비스
    "293490.KQ",  # 카카오게임즈
    "035900.KQ",  # JYP Ent
    "041510.KQ",  # SM
    "352820.KQ",  # 하이브(KOSDAQ)
    "035760.KQ",  # CJ ENM
    "112040.KQ",  # 위메이드
    "357780.KQ",  # 솔브레인
    "240810.KQ",  # 원익IPS
    "064760.KQ",  # 티씨케이
    "036930.KQ",  # 주성엔지니어링
    "140860.KQ",  # 파크시스템스
    "039030.KQ",  # 이오테크닉스
    "042700.KQ",  # 한미반도체
    # === S&P 500 추가 (나스닥 100 외) ===
    "BRK-B", "JPM", "V", "UNH", "JNJ", "WMT", "PG", "XOM",
    "MA", "HD", "CVX", "MRK", "ABBV", "LLY", "BAC", "PFE",
    "KO", "TMO", "DIS", "MCD", "WFC", "ABT", "DHR", "PM",
    "MS", "NEE", "UPS", "RTX", "LOW", "UNP", "GS", "BLK",
    "SPGI", "CAT", "SCHW", "DE", "AXP", "SYK", "LMT", "MDLZ",
    "AMT", "GILD", "CB", "CI", "MMC", "SO", "DUK", "ZTS",
    "CME", "ICE", "CL", "PGR", "APD", "FDX", "SHW", "MCK",
    "GE", "GM", "F", "BA", "SBUX", "NKE", "TGT", "COP",
]

_executor = ThreadPoolExecutor(max_workers=4)


# ── 점수 체계 ──
# 기술적(-7~+8), 재무(-4~+6), 거래량(-3~+4), 모멘텀/반등(0~+3),
# 최근트렌드(-3~+4), 뉴스(-3~+3)
# 합산 범위: -20 ~ +28
# BUY >= 5, SELL <= -5, 나머지 HOLD


def _score_technical(tech: dict, quote: dict) -> tuple[int, list[str]]:
    """
    기술적 지표 점수화 (추세 확인 중심).
    핵심 원칙: 추세 방향 확인 없이 반등을 기대하지 않음.
    반환: (score -8~+8, reasons)
    """
    score = 0
    reasons = []
    signals = tech.get("signals", {})
    price = tech.get("current_price")
    ma200 = tech.get("ma200")
    ma50 = tech.get("ma50")
    rsi = tech.get("rsi")
    rsi_change = tech.get("rsi_change_5d")
    ma20_slope = tech.get("ma20_slope")

    # 추세 방향 판단 (다른 지표의 조건으로 사용)
    ma_trend = signals.get("ma_trend")
    trend_up = ma_trend == "bullish"
    trend_down = ma_trend == "bearish"
    rsi_recovering = rsi_change is not None and rsi_change > 0
    slope_up = ma20_slope is not None and ma20_slope > 0

    # MA 추세 (+3/-3) — 가장 중요한 지표, 가중치 상향
    if trend_up:
        score += 3
        reasons.append("이동평균선 정배열 (상승추세)")
    elif trend_down:
        score -= 3
        reasons.append("이동평균선 역배열 (하락추세)")

    # 장기 MA200 (+1/-2) — 하락 시 더 큰 감점
    if price and ma200:
        if price > ma200:
            score += 1
            reasons.append("MA200 상회 (장기 강세)")
        else:
            score -= 2
            reasons.append("MA200 하회 (장기 약세)")

    # 데드크로스 (MA50 < MA200) — 장기 하락추세 감점
    if ma50 and ma200 and ma50 < ma200:
        score -= 1
        reasons.append("MA50 < MA200 데드크로스")

    # RSI — 추세 전환 확인 시에만 보너스
    rsi_signal = signals.get("rsi_signal")
    if rsi_signal == "oversold":
        if rsi_recovering and slope_up:
            # 과매도 + RSI 회복 + MA20 상승 = 진짜 반등
            score += 2
            reasons.append(f"RSI {rsi:.1f} 과매도 + 반등 확인")
        else:
            # 과매도지만 추세 전환 미확인 = 떨어지는 칼날
            score -= 1
            reasons.append(f"RSI {rsi:.1f} 과매도 — 추세 전환 미확인")
    elif rsi_signal == "overbought":
        score -= 1
        reasons.append(f"RSI {rsi:.1f} 과매수 주의")

    # MACD — 추세 방향과 일치할 때만 보너스
    macd_signal = signals.get("macd_signal")
    if macd_signal == "bullish":
        if not trend_down:  # 하락추세 아닐 때만
            score += 1
            reasons.append("MACD 골든크로스")
    elif macd_signal == "bearish":
        score -= 1
        reasons.append("MACD 데드크로스")

    # 볼린저밴드 — 추세 전환 확인 시에만 보너스
    bb_pos = signals.get("bb_position")
    if bb_pos == "below_lower":
        if rsi_recovering:
            score += 1
            reasons.append("볼린저밴드 하단 + 반등 시작")
        else:
            score -= 1
            reasons.append("볼린저밴드 하단 이탈 — 추가 하락 위험")
    elif bb_pos == "above_upper":
        score -= 1
        reasons.append("볼린저밴드 상단 — 과열 주의")

    # 52주 고가/저가 — 보수적 접근
    week52_high = quote.get("52_week_high")
    week52_low = quote.get("52_week_low")
    if price and week52_high and week52_low and week52_high > 0:
        pct_from_high = (price - week52_high) / week52_high
        pct_from_low = (price - week52_low) / week52_low if week52_low > 0 else 0

        if pct_from_high >= -0.05:
            score -= 1
            reasons.append("52주 고가 근접 — 상승 여력 제한")
        elif pct_from_low <= 0.10 and rsi_recovering and slope_up:
            # 52주 저가 근처 + 반등 확인 = 보너스
            score += 1
            reasons.append("52주 저가 근처 + 반등 확인")

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

        # 10년 백테스트 교정: 거래량 급증은 과열 신호 (적중률 54.8%)
        if vol_ratio > 2.0:
            if change > 0:
                score += 1  # 과열 가능, 축소 (3→1)
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x + 상승 — 과열 주의")
            elif change < -2:
                score -= 2
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x + 하락 — 투매 위험")
            else:
                score += 0
                reasons.append(f"거래량 급증 {vol_ratio:.1f}x — 관심 집중")
        elif vol_ratio > 1.5:
            if change > 0:
                score += 1  # (2→1)
                reasons.append(f"거래량 증가 {vol_ratio:.1f}x — 매수세 확인")
            elif change < -2:
                score -= 1
        elif vol_ratio < 0.5:
            score -= 1
            reasons.append("거래량 급감 — 관심 저하")

        # 추세 확인: 상승 + 거래량 증가 조합 추가 보너스
        if change > 1 and vol_ratio > 1.3:
            score += 1

    # 클램핑: -3 ~ +3 (거래량 과대평가 방지)
    score = max(-3, min(3, score))
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

    # 급락 후 반등은 RSI 회복 확인 시에만
    rsi_change = tech.get("rsi_change_5d")
    rsi_recovering = rsi_change is not None and rsi_change > 3

    if mom5 is not None and mom5 < -5 and near_low and rsi_recovering:
        score += 1
        reasons.append(f"5일 {mom5:+.1f}% 급락 후 RSI 회복 확인")

    if mom10 is not None and mom10 < -10 and near_low and rsi_recovering:
        score += 1
        reasons.append(f"10일 {mom10:+.1f}% 깊은 하락 후 반등 시작")

    # 연속 하락은 오히려 감점 (추세 전환 확인 전까지)
    if down_streak >= 5:
        score -= 1
        reasons.append(f"{down_streak}일 연속 하락 — 추세 하락 지속")

    # 클램핑: 0 ~ +3
    score = max(0, min(3, score))
    return score, reasons


def _score_recency(tech: dict, quote: dict) -> tuple[int, list[str]]:
    """
    최근 트렌드 가중 점수 — 단기 지표에 추가 비중.
    장기 지표(MA200, 52주)보다 최근 5~20일 변화를 더 반영.
    반환: (score -3~+4, reasons)
    """
    score = 0
    reasons = []

    rsi_change = tech.get("rsi_change_5d")
    ma20_slope = tech.get("ma20_slope")
    macd_accel = tech.get("macd_accel")
    trend_20d = tech.get("trend_20d")
    mom5 = tech.get("momentum_5d")

    # RSI 최근 방향: 5일간 RSI 상승/하락 추세
    if rsi_change is not None:
        if 3 <= rsi_change <= 15:
            score += 1
            reasons.append(f"RSI 5일 +{rsi_change:.0f} — 최근 매수세 유입")
        elif rsi_change < -10:
            score -= 1
            reasons.append(f"RSI 5일 {rsi_change:.0f} — 최근 매도 압력 급증")

    # MA20 기울기: 단기 추세 방향
    if ma20_slope is not None:
        if ma20_slope > 0.5:
            score += 1
            reasons.append(f"MA20 기울기 +{ma20_slope:.2f}% — 단기 상승 추세")
        elif ma20_slope < -0.5:
            score -= 1
            reasons.append(f"MA20 기울기 {ma20_slope:.2f}% — 단기 하락 추세")

    # MACD 가속도: 추세 변화 속도
    if macd_accel is not None:
        if macd_accel > 0.1:
            score += 1
            reasons.append("MACD 가속 — 상승 추세 강화 중")
        elif macd_accel < -0.3:
            score -= 1
            reasons.append("MACD 감속 — 추세 약화 경고")

    # 20일 추세 + 5일 모멘텀 조합: 조정 후 반등 (엄격한 조건)
    if trend_20d is not None and mom5 is not None:
        if trend_20d < -3 and mom5 > 2 and (ma20_slope is not None and ma20_slope > 0):
            score += 1  # 20일 하락 → 5일 강한 반등 + MA20 상승 전환
            reasons.append(f"20일 {trend_20d:+.1f}% 조정 후 반등 확인 (MA20 상승)")
        elif trend_20d < -5 and mom5 < -1:
            score -= 1  # 20일 급락 + 5일도 하락 = 추세 가속
            reasons.append(f"20일 {trend_20d:+.1f}% 급락 지속")

    score = max(-3, min(4, score))
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
        # BUY 확신도 (원점수 기반, 점수 차이 크게)
        if abs_score >= 12:
            base = 88
        elif abs_score >= 10:
            base = 83
        elif abs_score >= 8:
            base = 78
        elif abs_score >= 7:
            base = 73
        elif abs_score >= 6:
            base = 65
        else:
            base = 55  # score 5
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

        if total_score >= 5:  # BUY 품질 조정 (축소된 가중치)
            vol_ratio = tech.get("current_volume", 0) / tech.get("volume_ma20", 1) if tech.get("volume_ma20") else 1

            # 감점 요인 (위험 신호만 감점, 보너스 최소화)
            if volatility is not None and volatility > 4:
                base -= 8   # 고변동성 감점
            if vol_ratio > 2.0:
                base -= 4   # 거래량 급증 과열
            if bb_width is not None and bb_width > 15:
                base -= 4   # 극단적 BB 폭
            if down_streak >= 3:
                base -= 4   # 연속 하락
            if macd_accel is not None and macd_accel < -0.5:
                base -= 3   # 추세 악화
            if trend_20d is not None and 5 <= trend_20d <= 10:
                base -= 3   # 미지근한 상승

            # 보너스 (보수적, 최대 +4)
            bonus = 0
            if volatility is not None and 2 <= volatility <= 3:
                bonus += 2
            if trend_20d is not None and -5 <= trend_20d < 0:
                bonus += 2  # 조정 후 반등
            base += min(bonus, 4)

        elif total_score <= -5:  # SELL 품질 조정
            if volatility is not None and volatility > 5:
                base -= 5   # 고변동성에서 SELL도 불확실
            if macd_accel is not None and macd_accel < 0:
                base += 3   # 추세 악화 확인 → SELL 확신 증가

    return min(95, max(30, base))


def _analyze_single(ticker: str, include_news: bool = False) -> dict | None:
    """단일 종목 분석 (스레드에서 실행)."""
    import time as _time
    result = None
    for attempt in range(2):
        try:
            tech = get_technical_indicators(ticker)
            if "error" in tech:
                if attempt == 0:
                    _time.sleep(1)
                    continue
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

            # 5. 최근 트렌드 가중 (-3 ~ +4)
            rec_score, rec_reasons = _score_recency(tech, quote)

            # 6. 뉴스 점수 (-3 ~ +3) — 기본 스캔에서는 제외 (속도)
            news_score = 0
            news_reasons = []
            if include_news:
                try:
                    from services.news_service import get_news_headlines
                    headlines = get_news_headlines(ticker, limit=5)
                    news_score, news_reasons = _score_news(headlines)
                except Exception:
                    pass

            # 합산 (-20 ~ +28)
            total_score = tech_score + fin_score + vol_score + mom_score + rec_score + news_score

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
                "recency": rec_score,
                "news": news_score,
            }

            # === 추천 결정 ===
            rec = "HOLD"
            if total_score >= 5 and tech_score >= 0:
                rec = "BUY"
            elif total_score <= -5:
                rec = "SELL"

            # 시장 레짐 기반 BUY 억제
            try:
                from services.ml_service import get_current_market_features
                is_korean = ticker.endswith((".KS", ".KQ"))
                mkt = get_current_market_features(is_korean)
                mkt_breadth = mkt.get("market_breadth", 1.5)
                mkt_trend = mkt.get("market_trend_20d", 0)
                # 하락장: BUY 완전 차단
                if rec == "BUY" and mkt_breadth == 0:
                    rec = "HOLD"
                # 약세장: score 7~8은 HOLD로
                elif rec == "BUY" and mkt_breadth <= 1 and mkt_trend < -3 and total_score < 9:
                    rec = "HOLD"
            except Exception:
                pass

            # 6b. BUY 후보에 대해 뉴스 감성 2차 검증 (기본 스캔에서도 실행)
            if rec == "BUY" and not include_news:
                try:
                    from services.news_service import get_news_headlines
                    headlines = get_news_headlines(ticker, limit=5)
                    news_score, news_reasons = _score_news(headlines)
                    total_score += news_score
                    breakdown["news"] = news_score
                    # 악재 뉴스가 심하면 BUY → HOLD 다운그레이드
                    if news_score <= -2 or total_score < 5:
                        rec = "HOLD"
                except Exception:
                    pass

            # 모든 이유 합치기 (최대 5개)
            all_reasons = tech_reasons + fin_reasons + vol_reasons + mom_reasons + rec_reasons + news_reasons

            # ML 예측 우선, 폴백 규칙
            ml_conf = None
            if total_score >= 5:
                ml_features = {
                    "score": total_score,
                    "rsi": tech.get("rsi") or 0,
                    "vol_ratio": (tech.get("current_volume", 0) / tech.get("volume_ma20", 1)) if tech.get("volume_ma20") else 1,
                    "mom5": tech.get("momentum_5d") or 0,
                    "down_streak": tech.get("down_streak", 0),
                    "volatility": tech.get("volatility") or 0,
                    "bb_width": tech.get("bb_width") or 0,
                    "rsi_change": tech.get("rsi_change_5d") or 0,
                    "ma20_slope": tech.get("ma20_slope") or 0,
                    "macd_accel": tech.get("macd_accel") or 0,
                    "trend_20d": tech.get("trend_20d") or 0,
                    "tech_score": tech_score,
                    "fin_score": fin_score,
                    "vol_score": vol_score,
                }
                ml_conf = ml_predict(ml_features)
            confidence = ml_conf if ml_conf is not None else _calc_confidence(total_score, breakdown, tech)

            # BUY 시 익절/손절 가이드
            trade_guide = None
            if rec == "BUY":
                vol_pct = tech.get("volatility") or 3
                # 변동성 기반 동적 익절/손절
                if vol_pct < 2.5:
                    tp, sl = 3.0, -3.0
                elif vol_pct < 4:
                    tp, sl = 5.0, -5.0
                else:
                    tp, sl = 7.0, -7.0
                trade_guide = {
                    "take_profit": tp,
                    "stop_loss": sl,
                    "hold_days": 20,
                    "strategy": f"{tp:.0f}% 도달 시 익절, {sl:.0f}% 이탈 시 손절, 최대 20일 보유"
                }

            def _clean(v):
                """Replace NaN/Inf floats with None for JSON safety."""
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    return None
                return v

            return {
                "ticker": ticker,
                "name": quote.get("name") or ticker,
                "current_price": _clean(quote.get("current_price")),
                "change_percent": _clean(quote.get("change_percent")),
                "currency": quote.get("currency"),
                "recommendation": rec,
                "score": total_score,
                "max_score": 28,
                "confidence": confidence,
                "score_breakdown": breakdown,
                "reasons": all_reasons[:5],
                "rsi": _clean(tech.get("rsi")),
                "ma_trend": (tech.get("signals") or {}).get("ma_trend"),
                "pe_ratio": _clean(financials.get("pe_ratio")),
                "volume_ratio": _clean(vol_ratio),
                "trade_guide": trade_guide,
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

    # 메모리 캐시 없으면 디스크 캐시 확인
    if use_cache and _cache["data"] is None:
        disk = get_cached_result(_DISK_CACHE_KEY, CACHE_TTL)
        if disk is not None:
            _cache["data"] = disk["data"]
            _cache["timestamp"] = disk["timestamp"]
            return _cache["data"][:limit]

    # 이미 분석 진행 중이면 완료될 때까지 대기
    if use_cache and _progress["running"]:
        for _ in range(600):  # 최대 5분 대기
            await asyncio.sleep(0.5)
            if not _progress["running"]:
                break
        if _cache["data"] is not None:
            return _cache["data"][:limit]

    async with _analysis_lock:
        # 락 획득 후 다시 캐시 확인 (다른 요청이 이미 완료했을 수 있음)
        if use_cache and _cache["data"] is not None and (time.time() - _cache["timestamp"]) < CACHE_TTL:
            return _cache["data"][:limit]

        pool = tickers if tickers else DEFAULT_TICKERS
        include_news = tickers is not None and len(tickers) <= 10
        loop = asyncio.get_running_loop()

        # 진행률 초기화
        _progress["total"] = len(pool)
        _progress["done"] = 0
        _progress["success"] = 0
        _progress["failed"] = 0
        _progress["running"] = True
        _progress["failed_tickers"] = []

        def _tracked_analyze(t, news):
            result = _analyze_single(t, news)
            _progress["done"] += 1
            if result is not None:
                _progress["success"] += 1
            else:
                _progress["failed"] += 1
            return (t, result)

        # 배치 처리: Yahoo Finance rate limit 방지 (20개씩, 배치 간 3초 대기)
        BATCH_SIZE = 20
        results = []
        failed_tickers = []
        try:
            for i in range(0, len(pool), BATCH_SIZE):
                batch = pool[i:i + BATCH_SIZE]
                futures = [loop.run_in_executor(_executor, _tracked_analyze, t, include_news) for t in batch]
                raw = await asyncio.gather(*futures)
                for ticker, result in raw:
                    if result is not None:
                        results.append(result)
                    else:
                        failed_tickers.append(ticker)
                if i + BATCH_SIZE < len(pool):
                    await asyncio.sleep(3)
        finally:
            _progress["running"] = False
            _progress["failed_tickers"] = failed_tickers

    # BUY 우선, 점수 높은 순 정렬
    results.sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))

    if use_cache and results:
        _cache["data"] = results
        _cache["timestamp"] = time.time()
        set_cached_result(_DISK_CACHE_KEY, {"data": results, "timestamp": _cache["timestamp"]})

    return results[:limit]


async def retry_failed(limit: int = 300) -> list[dict]:
    """
    실패한 종목만 재분석하여 기존 캐시에 병합.
    실패 목록이 없으면 캐시 그대로 반환.
    """
    failed = list(_progress.get("failed_tickers", []))
    if not failed:
        # 실패한 종목 없음 → 캐시 반환
        if _cache["data"] is not None:
            return _cache["data"][:limit]
        return []

    async with _analysis_lock:
        # 락 획득 후 다시 확인
        failed = list(_progress.get("failed_tickers", []))
        if not failed:
            if _cache["data"] is not None:
                return _cache["data"][:limit]
            return []

        loop = asyncio.get_running_loop()

        _progress["total"] = len(failed)
        _progress["done"] = 0
        _progress["success"] = 0
        _progress["failed"] = 0
        _progress["running"] = True
        _progress["failed_tickers"] = []

        def _tracked_analyze(t):
            result = _analyze_single(t, False)
            _progress["done"] += 1
            if result is not None:
                _progress["success"] += 1
            else:
                _progress["failed"] += 1
            return (t, result)

        new_results = []
        still_failed = []
        BATCH_SIZE = 50
        try:
            for i in range(0, len(failed), BATCH_SIZE):
                batch = failed[i:i + BATCH_SIZE]
                futures = [loop.run_in_executor(_executor, _tracked_analyze, t) for t in batch]
                raw = await asyncio.gather(*futures)
                for ticker, result in raw:
                    if result is not None:
                        new_results.append(result)
                    else:
                        still_failed.append(ticker)
                if i + BATCH_SIZE < len(failed):
                    await asyncio.sleep(1)
        finally:
            _progress["running"] = False
            _progress["failed_tickers"] = still_failed

    # 기존 캐시에 새 결과 병합
    if _cache["data"] is not None:
        existing_tickers = {r["ticker"] for r in _cache["data"]}
        for r in new_results:
            if r["ticker"] not in existing_tickers:
                _cache["data"].append(r)
        _cache["data"].sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))
        _cache["timestamp"] = time.time()
        return _cache["data"][:limit]
    elif new_results:
        new_results.sort(key=lambda x: (0 if x["recommendation"] == "BUY" else 1 if x["recommendation"] == "HOLD" else 2, -x["score"]))
        _cache["data"] = new_results
        _cache["timestamp"] = time.time()
        return new_results[:limit]
    return []
