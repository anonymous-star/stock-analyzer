"""과거 데이터 기반 추천 시스템 백테스트."""

import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import yfinance as yf
import pandas as pd
import numpy as np
import math

from services.recommendation_service import DEFAULT_TICKERS
from services.cache_service import get_cached_history, set_cached_history, get_cached_result, set_cached_result
from services.ml_service import predict_confidence as ml_predict


def _fetch_history_cffi(ticker: str, period: str = "10y", interval: str = "1d") -> pd.DataFrame | None:
    """curl_cffi 기반 Yahoo Finance 직접 호출 (yfinance rate limit 우회)."""
    try:
        from curl_cffi import requests as cffi_requests
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        params = {"range": period, "interval": interval, "includePrePost": "false"}
        r = cffi_requests.get(url, params=params, impersonate="chrome", timeout=30)
        data = r.json()
        result = data["chart"]["result"][0]
        ts = result["timestamp"]
        quotes = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "Open": quotes["open"],
            "High": quotes["high"],
            "Low": quotes["low"],
            "Close": quotes["close"],
            "Volume": quotes["volume"],
        }, index=pd.to_datetime(ts, unit="s"))
        return df.dropna()
    except Exception:
        return None

# hold_days별 캐시: {hold_days: {"results": [...], "timestamp": float}}
_cache: dict[int, dict] = {}
CACHE_TTL = 24 * 3600  # 24시간 (10년 백테스트 데이터는 자주 안 바뀜)

# 백테스트 진행률
bt_progress = {"total": 0, "done": 0, "success": 0, "failed": 0, "running": False}
_bt_lock = asyncio.Lock()


def clear_backtest_cache():
    """추천 알고리즘 변경 시 캐시 초기화."""
    _cache.clear()

_executor = ThreadPoolExecutor(max_workers=4)


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
    """사전 계산된 지표에서 i번째 시점의 점수 계산.
    recommendation_service._score_technical/financial/volume/momentum/recency와 동일 로직.
    """
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

    # === 추세 방향 사전 계산 (recommendation_service와 동일) ===
    trend_up = not math.isnan(ma20) and not math.isnan(ma50) and price > ma20 > ma50
    trend_down = not math.isnan(ma20) and not math.isnan(ma50) and price < ma20 < ma50

    # RSI 5일 변화 (여러 곳에서 사용하므로 먼저 계산)
    _rsi_change_raw = None
    if i >= 5:
        _g2 = ind["rsi_gain"][i - 5]
        _l2 = ind["rsi_loss"][i - 5]
        _rs2 = _g2 / _l2 if _l2 != 0 else 100
        _rsi_prev = 100 - (100 / (1 + _rs2))
        _rsi_change_raw = rsi - _rsi_prev

    rsi_recovering = _rsi_change_raw is not None and _rsi_change_raw > 0

    # MA20 기울기 (여러 곳에서 사용)
    _ma20_slope_raw = None
    if i >= 5:
        _ma20_prev = ind["ma20"][i - 5]
        if _ma20_prev > 0 and not math.isnan(_ma20_prev):
            _ma20_slope_raw = (ma20 - _ma20_prev) / _ma20_prev * 100

    slope_up = _ma20_slope_raw is not None and _ma20_slope_raw > 0

    # MACD 가속도 (여러 곳에서 사용)
    _macd_accel_raw = None
    if i >= 1:
        _macd_accel_raw = ind["macd_hist"][i] - ind["macd_hist"][i - 1]

    # 모멘텀 관련 사전 계산
    c = ind["c"]
    mom5 = (price - c[i - 5]) / c[i - 5] * 100 if i >= 5 and c[i - 5] > 0 else 0
    mom10 = (price - c[i - 10]) / c[i - 10] * 100 if i >= 10 and c[i - 10] > 0 else 0
    down_streak = 0
    for j in range(i, max(i - 10, 0), -1):
        if c[j] < c[j - 1]:
            down_streak += 1
        else:
            break

    trend_20d_raw = None
    if i >= 20 and c[i - 20] > 0:
        trend_20d_raw = (price - c[i - 20]) / c[i - 20] * 100
    volatility_raw = ind["std20"][i] / price * 100 if price > 0 and not math.isnan(ind["std20"][i]) else None

    # === 기술적 점수 (recommendation_service._score_technical과 동일) ===
    tech_score = 0

    # MA 추세 (+3/-3) — 가장 중요한 지표
    if trend_up:
        tech_score += 3
    elif trend_down:
        tech_score -= 3

    # MA200 (+1/-2) — 하락 시 더 큰 감점
    if not math.isnan(ma200):
        if price > ma200:
            tech_score += 1
        else:
            tech_score -= 2

    # 데드크로스
    if not math.isnan(ma50) and not math.isnan(ma200) and ma50 < ma200:
        tech_score -= 1

    # RSI — 추세 전환 확인 시에만 보너스
    if rsi < 30:
        if rsi_recovering and slope_up:
            tech_score += 2  # 과매도 + 반등 확인
        else:
            tech_score -= 1  # 떨어지는 칼날
    elif rsi > 70:
        tech_score -= 1

    # MACD — 추세 방향과 일치할 때만
    if macd_l > sig_l:
        if not trend_down:
            tech_score += 1
    else:
        tech_score -= 1

    # 볼린저밴드 — 추세 전환 확인 시에만
    if price < bb_lower:
        if rsi_recovering:
            tech_score += 1
        else:
            tech_score -= 1
    elif price > bb_upper:
        tech_score -= 1

    # 52주 고저 — 보수적 접근
    pct_from_low = 999
    if yh > 0 and not math.isnan(yh):
        pct_from_high = (price - yh) / yh
        pct_from_low = (price - yl) / yl if yl > 0 else 0
        if pct_from_high >= -0.05:
            tech_score -= 1
        elif pct_from_low <= 0.10 and rsi_recovering and slope_up:
            tech_score += 1  # 52주 저가 + 반등 확인

    near_low = pct_from_low < 0.30

    # === 거래량 점수 (recommendation_service._score_volume과 동일) ===
    vol_score = 0
    prev_price = ind["c"][i - 1] if i > 0 else price
    day_change = (price - prev_price) / prev_price * 100 if prev_price > 0 else 0
    if vol_ratio > 2.0:
        if day_change > 0:
            vol_score += 1
        elif day_change < -2:
            vol_score -= 2
    elif vol_ratio > 1.5:
        if day_change > 0:
            vol_score += 1
        elif day_change < -2:
            vol_score -= 1
    elif vol_ratio < 0.5:
        vol_score -= 1
    if day_change > 1 and vol_ratio > 1.3:
        vol_score += 1
    vol_score = max(-3, min(3, vol_score))

    # === 모멘텀 점수 (recommendation_service._score_momentum과 동일) ===
    mom_score = 0
    rsi_recovering_strong = _rsi_change_raw is not None and _rsi_change_raw > 3

    if mom5 < -5 and near_low and rsi_recovering_strong:
        mom_score += 1
    if mom10 < -10 and near_low and rsi_recovering_strong:
        mom_score += 1
    if down_streak >= 5:
        mom_score -= 1  # 연속 하락은 감점
    mom_score = max(0, min(3, mom_score))

    # === 최근 트렌드 점수 (recommendation_service._score_recency와 동일) ===
    rec_score = 0

    if _rsi_change_raw is not None:
        if 3 <= _rsi_change_raw <= 15:
            rec_score += 1
        elif _rsi_change_raw < -10:
            rec_score -= 1

    if _ma20_slope_raw is not None:
        if _ma20_slope_raw > 0.5:
            rec_score += 1
        elif _ma20_slope_raw < -0.5:
            rec_score -= 1

    if _macd_accel_raw is not None:
        if _macd_accel_raw > 0.1:
            rec_score += 1
        elif _macd_accel_raw < -0.3:
            rec_score -= 1

    # 20일 하락 + 5일 반등 (엄격한 조건)
    if trend_20d_raw is not None and mom5 is not None:
        if trend_20d_raw < -3 and mom5 > 2 and slope_up:
            rec_score += 1
        elif trend_20d_raw < -5 and mom5 < -1:
            rec_score -= 1
    rec_score = max(-3, min(4, rec_score))

    # === 합산 ===
    score = tech_score + vol_score + mom_score + rec_score

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
        "tech_score": tech_score,
        "vol_score": vol_score,
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

    if score >= 5:  # BUY
        # 기본 점수: 원점수 기반 (점수 차이를 크게)
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

        # 품질 조정 (축소된 가중치, 감점 위주)
        volatility = signals.get("volatility")
        bb_width = signals.get("bb_width")
        mom5 = signals.get("mom5", 0)
        macd_accel = signals.get("macd_accel")
        down_streak = signals.get("down_streak", 0)
        trend_20d = signals.get("trend_20d")
        vol_ratio = signals.get("vol_ratio", 1.0)

        # 감점 요인 (위험 신호만 감점, 보너스 최소화)
        if volatility is not None and volatility > 4:
            base -= 8   # 고변동성 감점 (15→8)
        if vol_ratio > 2.0:
            base -= 4   # 거래량 급증 과열 (6→4)
        if bb_width is not None and bb_width > 15:
            base -= 4   # 극단적 BB 폭 (8→4)
        if down_streak >= 3:
            base -= 4   # 연속 하락 (5→4)
        if macd_accel is not None and macd_accel < -0.5:
            base -= 3   # 추세 악화 (4→3)
        if trend_20d is not None and 5 <= trend_20d <= 10:
            base -= 3   # 미지근한 상승 (4→3)

        # 보너스 (보수적, 최대 +4)
        bonus = 0
        if volatility is not None and 2 <= volatility <= 3:
            bonus += 2
        if trend_20d is not None and -5 <= trend_20d < 0:
            bonus += 2  # 조정 후 반등
        base += min(bonus, 4)

    elif score <= -5:  # SELL
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
        # 10년 데이터 캐시 우선 (가장 큰 효과)
        df = get_cached_history(ticker, "10y", "1d")
        if df is None:
            try:
                stock = yf.Ticker(ticker)
                df = stock.history(period="10y", interval="1d")
            except Exception:
                df = None
            # yfinance 실패 시 curl_cffi 폴백
            if df is None or df.empty:
                df = _fetch_history_cffi(ticker, "10y", "1d")
            if df is not None and not df.empty:
                set_cached_history(ticker, "10y", "1d", df)
        if df is None or df.empty or len(df) < 220:
            return None

        close = df["Close"]
        volume = df["Volume"]

        # 전체 지표 한 번만 계산
        ind = _precompute_indicators(close, volume)

        trades = {"BUY": [], "HOLD": [], "SELL": []}
        buy_by_tier = {"매우 강력": [], "강력": [], "양호": [], "보통": []}
        buy_opportunities = []  # (max_return, tp_return) 수익 기회 추적
        total_signals = 0
        close_arr = close.values.astype(float)

        # 7일 간격 샘플링 (10년 데이터 최적화)
        for i in range(200, len(df) - hold_days, sample_interval):
            signals = _score_at(ind, i)
            if signals is None:
                continue

            score = signals["score"]
            entry_price = signals["price"]
            exit_price = float(close_arr[i + hold_days])
            ret = (exit_price - entry_price) / entry_price * 100

            # 백테스트 임계값 (recommendation_service와 동일)
            is_buy = score >= 5
            if is_buy:
                rec = "BUY"
                # ML 예측 우선, 폴백 규칙
                ml_features = {**signals}
                ml_conf = ml_predict(ml_features)
                confidence = ml_conf if ml_conf is not None else _calc_backtest_confidence(score, signals)
                tier = _confidence_tier(confidence)
                buy_by_tier[tier].append(ret)

                # 수익 기회 분석 + 동적 손절 시뮬레이션
                window = close_arr[i + 1: i + hold_days + 1]
                max_price = float(np.max(window))
                min_price = float(np.min(window))
                max_ret = (max_price - entry_price) / entry_price * 100
                min_ret = (min_price - entry_price) / entry_price * 100

                # 변동성 기반 동적 SL (익절 없음 = 수익 무제한)
                vol = signals.get("volatility") or 3.0
                if vol < 2.5:
                    sl_pct = -3.0
                elif vol < 4.0:
                    sl_pct = -5.0
                else:
                    sl_pct = -7.0

                sl_ret = ret  # 기본은 만기 수익
                for j in range(len(window)):
                    day_ret = (float(window[j]) - entry_price) / entry_price * 100
                    if day_ret <= sl_pct:
                        sl_ret = sl_pct
                        break
                buy_opportunities.append((max_ret, sl_ret, min_ret))

            elif score <= -5:
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

        # BUY 수익 기회 + 동적 손절 통계
        buy_opp = {}
        if buy_opportunities:
            max_rets = [o[0] for o in buy_opportunities]
            sl_rets = [o[1] for o in buy_opportunities]
            min_rets = [o[2] for o in buy_opportunities]
            opp_1pct = sum(1 for r in max_rets if r >= 1.0)
            opp_3pct = sum(1 for r in max_rets if r >= 3.0)
            sl_wins = sum(1 for r in sl_rets if r > 0)
            sl_stopped = sum(1 for r in sl_rets if r < -2.5)
            buy_opp = {
                "opportunity_1pct": round(opp_1pct / len(max_rets) * 100, 1),
                "opportunity_3pct": round(opp_3pct / len(max_rets) * 100, 1),
                "avg_max_return": round(sum(max_rets) / len(max_rets), 2),
                "avg_max_drawdown": round(sum(min_rets) / len(min_rets), 2),
                "sl_avg_return": round(sum(sl_rets) / len(sl_rets), 2),
                "sl_hit_rate": round(sl_wins / len(sl_rets) * 100, 1),
                "sl_stop_rate": round(sl_stopped / len(sl_rets) * 100, 1),
                "buy_hold_avg_return": buy_stats["avg_return"],
            }

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
            "buy_opportunity": buy_opp,
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

    # 메모리 캐시 없으면 디스크 캐시 확인
    disk_key = f"backtest:{hold_days}"
    disk = get_cached_result(disk_key, CACHE_TTL)
    if disk is not None:
        _cache[hold_days] = disk
        return disk["results"][:limit]

    # 이미 백테스트 진행 중이면 완료 대기
    if bt_progress["running"]:
        for _ in range(600):
            await asyncio.sleep(0.5)
            if not bt_progress["running"]:
                break
        cached = _cache.get(hold_days)
        if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
            return cached["results"][:limit]

    async with _bt_lock:
        # 락 획득 후 캐시 재확인
        cached = _cache.get(hold_days)
        if cached and (time.time() - cached["timestamp"]) < CACHE_TTL:
            return cached["results"][:limit]

        pool = DEFAULT_TICKERS
        loop = asyncio.get_running_loop()

        bt_progress["total"] = len(pool)
        bt_progress["done"] = 0
        bt_progress["success"] = 0
        bt_progress["failed"] = 0
        bt_progress["running"] = True

        def _tracked_backtest(t, hd):
            result = _backtest_ticker(t, hd)
            bt_progress["done"] += 1
            if result is not None:
                bt_progress["success"] += 1
            else:
                bt_progress["failed"] += 1
            return result

        results = []
        BATCH_SIZE = 50
        try:
            for i in range(0, len(pool), BATCH_SIZE):
                batch = pool[i:i + BATCH_SIZE]
                futures = [loop.run_in_executor(_executor, _tracked_backtest, t, hold_days) for t in batch]
                raw = await asyncio.gather(*futures)
                results.extend([r for r in raw if r is not None])
                if i + BATCH_SIZE < len(pool):
                    await asyncio.sleep(1)
        finally:
            bt_progress["running"] = False

    results.sort(key=lambda x: -x["accuracy"])

    _cache[hold_days] = {"results": results, "timestamp": time.time()}
    set_cached_result(f"backtest:{hold_days}", _cache[hold_days])

    return results[:limit]
