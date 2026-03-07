"""뉴스 헤드라인 감성 분석 (키워드 기반, 외부 의존성 없음)."""

# 긍정 키워드 (한국어 + 영어)
POSITIVE_KEYWORDS = [
    # 한국어
    "급등", "상승", "호재", "최고가", "돌파", "반등", "성장", "흑자", "수주",
    "매수", "목표가 상향", "상향", "실적 개선", "호실적", "사상 최대",
    "기대감", "수혜", "긍정", "추천", "강세",
    # 영어
    "surge", "rally", "soar", "beat", "upgrade", "outperform", "bullish",
    "record high", "breakout", "growth", "profit", "buy", "strong",
    "positive", "upside", "momentum", "opportunity",
]

# 부정 키워드
NEGATIVE_KEYWORDS = [
    # 한국어
    "급락", "하락", "악재", "최저가", "폭락", "적자", "감소", "매도",
    "목표가 하향", "하향", "실적 부진", "리스크", "우려", "위기",
    "조정", "약세", "손실", "둔화", "불확실",
    # 영어
    "crash", "plunge", "drop", "miss", "downgrade", "underperform", "bearish",
    "record low", "decline", "loss", "sell", "weak", "negative",
    "downside", "risk", "warning", "cut", "layoff", "bankruptcy",
]

# 강한 긍정/부정 (가중치 2)
STRONG_POSITIVE = ["급등", "사상 최대", "돌파", "surge", "record high", "breakout"]
STRONG_NEGATIVE = ["급락", "폭락", "적자", "crash", "plunge", "bankruptcy"]


def score_headlines(headlines: list[str]) -> tuple[int, str]:
    """
    헤드라인 목록의 감성 점수 계산.

    Returns:
        (score: -3~+3, summary: 요약 문자열)
    """
    if not headlines:
        return 0, "뉴스 없음"

    total = 0
    pos_count = 0
    neg_count = 0

    for headline in headlines:
        h_lower = headline.lower()

        for kw in STRONG_POSITIVE:
            if kw in h_lower:
                total += 2
                pos_count += 1
                break
        else:
            for kw in POSITIVE_KEYWORDS:
                if kw in h_lower:
                    total += 1
                    pos_count += 1
                    break

        for kw in STRONG_NEGATIVE:
            if kw in h_lower:
                total -= 2
                neg_count += 1
                break
        else:
            for kw in NEGATIVE_KEYWORDS:
                if kw in h_lower:
                    total -= 1
                    neg_count += 1
                    break

    # -3 ~ +3 범위로 클램핑
    score = max(-3, min(3, total))

    if score >= 2:
        summary = f"매우 긍정적 뉴스 (긍정 {pos_count}건, 부정 {neg_count}건)"
    elif score >= 1:
        summary = f"긍정적 뉴스 (긍정 {pos_count}건, 부정 {neg_count}건)"
    elif score <= -2:
        summary = f"매우 부정적 뉴스 (긍정 {pos_count}건, 부정 {neg_count}건)"
    elif score <= -1:
        summary = f"부정적 뉴스 (긍정 {pos_count}건, 부정 {neg_count}건)"
    else:
        summary = f"중립적 뉴스 (긍정 {pos_count}건, 부정 {neg_count}건)"

    return score, summary
