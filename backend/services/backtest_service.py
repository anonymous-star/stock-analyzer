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


def _precompute_indicators(close: pd.Series, volume: pd.Series) -> dict:
    """전체 시리즈에 대해 지표를 한 번만 계산."""
    import numpy as np
    n = len(close)
    c = close.values.astype(float)
    v = volume.values.astype(float)

    ma20 = close.rolling(20).mean().values
    ma50 = close.rolling(50).mean().values
    ma200 = close.rolling(200).mean().values
    bb_std = close.rolling(20).std().values

    # RSI (전체)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean().values
    loss = (-delta.clip(upper=0)).rolling(14).mean().values

    # Volume MA20
    vol_ma20 = volume.rolling(20).mean().values

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = (ema12 - ema26).values
    signal_line = (ema12 - ema26).ewm(span=9, adjust=False).mean().values
    macd_hist = macd_line - signal_line

    # 52주 rolling high/low
    year_high = close.rolling(252, min_periods=200).max().values
    year_low = close.rolling(252, min_periods=200).min().values

    # Volatility (20일 std / price %)
    std20 = close.rolling(20).std().values

    return {
        "c": c, "v": v, "n": n,
        "ma20": ma20, "ma50": ma50, "ma200": ma200,
        "bb_std": bb_std,
        "rsi_gain": gain, "rsi_loss": loss,
        "vol_ma20": vol_ma20,
        "macd_line": macd_line, "signal_line": signal_line, "macd_hist": macd_hist,
        "year_high": year_high, "year_low": year_low,
        "std20": std20,
    }


def _score_at(ind: dict, i: int) -> dict | None:
    """사전 계산된 지표에서 i번째 시점의 점수 계산."""
    if i < 200 or i >= ind["n"]:
        return None

    price = ind["c"][i]
    if price <= 0 or math.isnan(price):
        return None

    ma20 = ind["ma20"][i]
    ma50 = ind["ma50"][i]
    ma200 = ind["ma200"][i]

    # RSI
    g = ind["rsi_gain"][i]
    l = ind["rsi_loss"][i]
    rs = g / l if l != 0 else 100
    rsi = 100 - (100 / (1 + rs))

    # Volume
    vol_ma20 = ind["vol_ma20"][i]
    current_vol = ind["v"][i]
    vol_ratio = current_vol / vol_ma20 if vol_ma20 > 0 else 1.0

    # MACD
    macd_l = ind["macd_line"][i]
    sig_l = ind["signal_line"][i]

    # BB
    bb_mid = ma20
    bb_s = ind["bb_std"][i]
    bb_upper = bb_mid + 2 * bb_s
    bb_lower = bb_mid - 2 * bb_s

    # 52주
    yh = ind["year_high"][i]
    yl = ind["year_low"][i]

    # === 점수 계산 ===
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
    if macd_l > sig_l:
        score += 1
    else:
        score -= 1

    # BB (+2/-1)
    if price < bb_lower:
        score += 2
    elif price > bb_upper:
        score -= 1

    # 52주 고저
    pct_from_low = 999
    if yh > 0 and not math.isnan(yh):
        pct_from_high = (price - yh) / yh
        pct_from_low = (price - yl) / yl if yl > 0 else 0
        if pct_from_high >= -0.05:
            score -= 1
        elif pct_from_low <= 0.10:
            score += 2
        elif pct_from_low <= 0.30:
            score += 1

    near_low = pct_from_low < 0.30

    # 거래량 (-3~+4)
    prev_price = ind["c"][i - 1] if i > 0 else price
    day_change = (price - prev_price) / prev_price * 100 if prev_price > 0 else 0
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

    # 모멘텀/반등 보호
    c = ind["c"]
    mom5 = (price - c[i - 5]) / c[i - 5] * 100 if i >= 5 and c[i - 5] > 0 else 0
    mom10 = (price - c[i - 10]) / c[i - 10] * 100 if i >= 10 and c[i - 10] > 0 else 0
    down_streak = 0
    for j in range(i, max(i - 10, 0), -1):
        if c[j] < c[j - 1]:
            down_streak += 1
        else:
            break

    if mom5 < -5 and near_low:
        score += 1
    if mom10 < -10 and near_low:
        score += 1
    if down_streak >= 3 and near_low:
        score += 1

    # 품질 지표
    volatility = None
    s20 = ind["std20"][i]
    if not math.isnan(s20) and price > 0:
        volatility = round(s20 / price * 100, 2)

    bb_width = round((bb_upper - bb_lower) / bb_mid * 100, 2) if bb_mid > 0 else None

    # RSI 변화 (5일 전 RSI)
    rsi_change = None
    if i >= 5:
        g2 = ind["rsi_gain"][i - 5]
        l2 = ind["rsi_loss"][i - 5]
        rs2 = g2 / l2 if l2 != 0 else 100
        rsi_prev = 100 - (100 / (1 + rs2))
        rsi_change = round(rsi - rsi_prev, 1)

    # MA20 기울기
    ma20_slope = None
    if i >= 5:
        ma20_prev = ind["ma20"][i - 5]
        if ma20_prev > 0 and not math.isnan(ma20_prev):
            ma20_slope = round((ma20 - ma20_prev) / ma20_prev * 100, 3)

    # MACD 가속도
    macd_accel = None
    if i >= 1:
        macd_accel = round(ind["macd_hist"][i] - ind["macd_hist"][i - 1], 4)

    # 20일 추세
    trend_20d = None
    if i >= 20 and c[i - 20] > 0:
        trend_20d = round((price - c[i - 20]) / c[i - 20] * 100, 2)

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


def _backtest_ticker(ticker: str, hold_days: int = 20, sample_interval: int = 7) -> dict | None:
    """단일 종목 백테스트: 10년 슬라이딩 윈도우 (7일 간격 샘플링)."""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="10y", interval="1d")
        if df.empty or len(df) < 220:
            return None

        close = df["Close"]
        volume = df["Volume"]

        # 전체 지표 한 번만 계산
        ind = _precompute_indicators(close, volume)

        trades = {"BUY": [], "HOLD": [], "SELL": []}
        buy_by_tier = {"매우 강력": [], "강력": [], "양호": [], "보통": []}
        total_signals = 0

        # 7일 간격 샘플링 (10년 데이터 최적화)
        for i in range(200, len(df) - hold_days, sample_interval):
            signals = _score_at(ind, i)
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
