"""과거 데이터 기반 추천 시스템 백테스트."""

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import pandas as pd
import math

from services.recommendation_service import DEFAULT_TICKERS

# hold_days별 캐시: {hold_days: {"results": [...], "timestamp": float}}
_cache: dict[int, dict] = {}
CACHE_TTL = 28800  # 8시간


def clear_backtest_cache():
    """추천 알고리즘 변경 시 캐시 초기화."""
    _cache.clear()

_executor = ThreadPoolExecutor(max_workers=8)


def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def _compute_signals_at(close: pd.Series, volume: pd.Series, idx: int) -> dict | None:
    """주어진 인덱스 시점의 기술적+거래량 신호 계산."""
    if idx < 200:
        return None

    window = close.iloc[:idx + 1]
    vol_window = volume.iloc[:idx + 1]
    price = float(window.iloc[-1])

    ma20 = float(window.rolling(20).mean().iloc[-1])
    ma50 = float(window.rolling(50).mean().iloc[-1])
    ma200 = float(window.rolling(200).mean().iloc[-1])

    # RSI
    delta = window.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
    rsi = 100 - (100 / (1 + rs))

    # 거래량
    vol_ma20 = float(vol_window.rolling(20).mean().iloc[-1])
    current_vol = float(vol_window.iloc[-1])
    vol_ratio = current_vol / vol_ma20 if vol_ma20 > 0 else 1.0

    # MACD
    ema12 = float(window.ewm(span=12, adjust=False).mean().iloc[-1])
    ema26 = float(window.ewm(span=26, adjust=False).mean().iloc[-1])
    macd_line = ema12 - ema26
    signal_line = float((window.ewm(span=12, adjust=False).mean() - window.ewm(span=26, adjust=False).mean()).ewm(span=9, adjust=False).mean().iloc[-1])

    # 볼린저밴드
    bb_mid = float(window.rolling(20).mean().iloc[-1])
    bb_std = float(window.rolling(20).std().iloc[-1])
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    # 52주 고저
    year_high = float(window.max())
    year_low = float(window.min())

    # 점수 계산 (기술적 + 거래량, 실제 추천과 동일 로직)
    score = 0

    # MA 추세 (+2/-2)
    if price > ma20 > ma50:
        score += 2
    elif price < ma20 < ma50:
        score -= 2

    # MA200 (+1/-1)
    if price > ma200:
        score += 1
    else:
        score -= 1

    # RSI (+2/-1)
    if rsi < 30:
        score += 2
    elif rsi > 70:
        score -= 1

    # MACD (+1/-1)
    if macd_line > signal_line:
        score += 1
    else:
        score -= 1

    # 볼린저밴드 (+2/-1)
    if price < bb_lower:
        score += 2
    elif price > bb_upper:
        score -= 1

    # 52주 고저 (강화된 반등 보호)
    pct_from_low = 999
    if year_high > 0:
        pct_from_high = (price - year_high) / year_high
        pct_from_low = (price - year_low) / year_low if year_low > 0 else 0
        if pct_from_high >= -0.05:
            score -= 1
        elif pct_from_low <= 0.10:  # 52주 저가 10% 이내
            score += 2
        elif pct_from_low <= 0.30:  # 52주 저가 30% 이내
            score += 1

    near_low = pct_from_low < 0.30

    # 거래량 (-3~+4)
    day_change = (price - float(window.iloc[-2])) / float(window.iloc[-2]) * 100 if len(window) > 1 else 0
    if vol_ratio > 2.0:
        if day_change > 0:
            score += 3
        elif day_change < -2:
            score -= 2
        else:
            score += 1
    elif vol_ratio > 1.5:
        if day_change > 0:
            score += 2
        elif day_change < -2:
            score -= 1
    elif vol_ratio < 0.5:
        score -= 1
    if day_change > 1 and vol_ratio > 1.3:
        score += 1

    # 모멘텀/반등 보호 (0 ~ +3) — 52주 저가 근처에서만 작동
    mom5 = (price - float(window.iloc[-6])) / float(window.iloc[-6]) * 100 if len(window) > 5 else 0
    mom10 = (price - float(window.iloc[-11])) / float(window.iloc[-11]) * 100 if len(window) > 10 else 0
    down_streak = 0
    for j in range(len(window) - 1, max(len(window) - 11, 0), -1):
        if float(window.iloc[j]) < float(window.iloc[j - 1]):
            down_streak += 1
        else:
            break

    if mom5 < -5 and near_low:
        score += 1
    if mom10 < -10 and near_low:
        score += 1
    if down_streak >= 3 and near_low:
        score += 1

    # 추가 품질 지표 (10년 교정용)
    # 변동성 (20일 std / price %)
    volatility = None
    if len(window) >= 20:
        std20 = float(window.tail(20).std())
        volatility = round(std20 / price * 100, 2) if price > 0 else None

    # BB 폭 (%)
    bb_width = None
    if bb_mid > 0:
        bb_width = round((bb_upper - bb_lower) / bb_mid * 100, 2)

    # RSI 변화 (5일)
    rsi_change = None
    if len(window) > 19:
        try:
            prev_w = window.iloc[:-5]
            d2 = prev_w.diff()
            g2 = d2.clip(lower=0).rolling(14).mean()
            l2 = (-d2.clip(upper=0)).rolling(14).mean()
            rs2 = g2.iloc[-1] / l2.iloc[-1] if l2.iloc[-1] != 0 else 100
            rsi_prev = 100 - (100 / (1 + rs2))
            rsi_change = round(rsi - rsi_prev, 1)
        except Exception:
            pass

    # MA20 기울기 (5일 변화 %)
    ma20_slope = None
    if len(window) >= 25:
        ma20_prev = float(window.iloc[:-5].rolling(20).mean().iloc[-1])
        if ma20_prev > 0:
            ma20_slope = round((ma20 - ma20_prev) / ma20_prev * 100, 3)

    # MACD 가속도
    macd_accel = None
    if len(window) >= 2:
        try:
            macd_series = window.ewm(span=12, adjust=False).mean() - window.ewm(span=26, adjust=False).mean()
            hist_series = macd_series - macd_series.ewm(span=9, adjust=False).mean()
            macd_accel = round(float(hist_series.iloc[-1]) - float(hist_series.iloc[-2]), 4)
        except Exception:
            pass

    # 20일 추세 (%)
    trend_20d = None
    if len(window) >= 21:
        price_20d_ago = float(window.iloc[-21])
        if price_20d_ago > 0:
            trend_20d = round((price - price_20d_ago) / price_20d_ago * 100, 2)

    return {
        "price": price,
        "score": score,
        "rsi": round(rsi, 1),
        "vol_ratio": round(vol_ratio, 2),
        "mom5": round(mom5, 2),
        "down_streak": down_streak,
        "volatility": volatility,
        "bb_width": bb_width,
        "rsi_change": rsi_change,
        "ma20_slope": ma20_slope,
        "macd_accel": macd_accel,
        "trend_20d": trend_20d,
    }


def _calc_backtest_confidence(score: int, signals: dict) -> int:
    """백테스트용 확신도 계산 (_calc_confidence와 동일 로직)."""
    abs_score = abs(score)

    if score >= 4:  # BUY
        if abs_score >= 12:
            base = 85
        elif abs_score >= 10:
            base = 80
        elif abs_score >= 8:
            base = 76
        elif abs_score >= 6:
            base = 72
        elif abs_score >= 4:
            base = 60
        else:
            base = 55

        # 품질 조정 (10년 160건 교정)
        volatility = signals.get("volatility")
        bb_width = signals.get("bb_width")
        rsi_change = signals.get("rsi_change")
        ma20_slope = signals.get("ma20_slope")
        mom5 = signals.get("mom5", 0)
        macd_accel = signals.get("macd_accel")
        down_streak = signals.get("down_streak", 0)
        trend_20d = signals.get("trend_20d")

        if volatility is not None:
            if volatility > 4:
                base -= 12
            elif 2 <= volatility <= 3:
                base += 3
            elif volatility <= 4:
                base += 1

        if bb_width is not None:
            if bb_width > 12:
                base -= 8
            elif 8 <= bb_width <= 12:
                base += 2

        if rsi_change is not None:
            if rsi_change < -5:
                base -= 6
            elif 0 <= rsi_change <= 5:
                base += 3
            elif rsi_change > 5:
                base -= 3

        if ma20_slope is not None:
            if 0 < ma20_slope <= 0.5:
                base -= 6
            elif ma20_slope > 1:
                base += 2

        if mom5 is not None:
            if 0 <= mom5 < 3:
                base -= 5
            elif mom5 >= 3:
                base += 3
            elif mom5 < -5:
                base -= 6

        if trend_20d is not None:
            if 5 <= trend_20d <= 10:
                base -= 6
            elif -5 <= trend_20d < 0:
                base += 4

        if macd_accel is not None:
            if macd_accel >= 0.5:
                base += 3
            elif macd_accel >= 0.1:
                base += 1
            elif macd_accel < -0.5:
                base -= 4

        if down_streak >= 3:
            base -= 5
        elif down_streak >= 2:
            base -= 3

    elif score <= -4:  # SELL
        if abs_score >= 10:
            base = 80
        elif abs_score >= 8:
            base = 75
        elif abs_score >= 6:
            base = 70
        else:
            base = 65

        volatility = signals.get("volatility")
        macd_accel = signals.get("macd_accel")
        if volatility is not None and volatility > 5:
            base -= 5
        if macd_accel is not None and macd_accel < 0:
            base += 3
    else:
        base = 50

    return min(95, max(30, base))


def _confidence_tier(confidence: int) -> str:
    if confidence >= 80:
        return "매우 강력"
    elif confidence >= 70:
        return "강력"
    elif confidence >= 55:
        return "양호"
    else:
        return "보통"


def _backtest_ticker(ticker: str, hold_days: int = 20, sample_interval: int = 3) -> dict | None:
    """단일 종목 백테스트: 1년 슬라이딩 윈도우."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y", interval="1d")
        if df.empty or len(df) < 220:
            return None

        close = df["Close"]
        volume = df["Volume"]

        trades = {"BUY": [], "HOLD": [], "SELL": []}
        # 확신도 티어별 BUY 적중률 추적
        buy_by_tier = {"매우 강력": [], "강력": [], "양호": [], "보통": []}
        total_signals = 0

        # 3일 간격 샘플링
        for i in range(200, len(df) - hold_days, sample_interval):
            signals = _compute_signals_at(close, volume, i)
            if signals is None:
                continue

            score = signals["score"]
            entry_price = signals["price"]
            exit_price = float(close.iloc[i + hold_days])
            ret = (exit_price - entry_price) / entry_price * 100

            # 백테스트 임계값 (반등 보호 반영, SELL은 더 엄격)
            if score >= 4:
                rec = "BUY"
                confidence = _calc_backtest_confidence(score, signals)
                tier = _confidence_tier(confidence)
                buy_by_tier[tier].append(ret)
            elif score <= -4:
                rec = "SELL"
            else:
                rec = "HOLD"

            trades[rec].append(ret)
            total_signals += 1

        if total_signals == 0:
            return None

        def _stats(rets: list[float]) -> dict:
            if not rets:
                return {"count": 0, "avg_return": 0, "hit_rate": 0}
            hits = sum(1 for r in rets if r > 0)
            return {
                "count": len(rets),
                "avg_return": round(sum(rets) / len(rets), 2),
                "hit_rate": round(hits / len(rets) * 100, 1),
            }

        buy_stats = _stats(trades["BUY"])
        sell_stats = _stats(trades["SELL"])
        hold_stats = _stats(trades["HOLD"])

        # 확신도 티어별 BUY 성과
        buy_tiers = {}
        for tier, rets in buy_by_tier.items():
            if rets:
                buy_tiers[tier] = _stats(rets)

        # 종합 적중률: BUY 신호가 실제 수익, SELL 신호가 실제 손실
        all_rets = trades["BUY"] + trades["HOLD"] + trades["SELL"]
        buy_correct = sum(1 for r in trades["BUY"] if r > 0)
        sell_correct = sum(1 for r in trades["SELL"] if r < 0)
        total_directional = len(trades["BUY"]) + len(trades["SELL"])
        accuracy = round((buy_correct + sell_correct) / total_directional * 100, 1) if total_directional > 0 else 0

        name = ticker
        try:
            info = stock.fast_info
            name = ticker  # fast_info doesn't have name
        except Exception:
            pass

        return {
            "ticker": ticker,
            "name": name,
            "hold_days": hold_days,
            "total_signals": total_signals,
            "accuracy": accuracy,
            "avg_return": round(sum(all_rets) / len(all_rets), 2) if all_rets else 0,
            "buy": buy_stats,
            "sell": sell_stats,
            "hold": hold_stats,
            "buy_tiers": buy_tiers,
        }
    except Exception:
        return None


async def run_backtest(hold_days: int = 20, limit: int = 10) -> list[dict]:
    """
    전체 종목 대상 백테스트 실행.
    보유 일수별 8시간 캐시.
    """
    cached = _cache.get(hold_days)
    if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
        return cached["results"][:limit]

    pool = DEFAULT_TICKERS
    loop = asyncio.get_event_loop()

    futures = [loop.run_in_executor(_executor, _backtest_ticker, t, hold_days) for t in pool]
    raw = await asyncio.gather(*futures)

    results = [r for r in raw if r is not None]
    results.sort(key=lambda x: -x["accuracy"])

    _cache[hold_days] = {"results": results, "timestamp": time.time()}

    return results[:limit]
