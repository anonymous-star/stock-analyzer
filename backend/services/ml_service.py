"""하이브리드 적중률 극대화 모델 v6.

v5 → v6 핵심 변경:
- 시장 레짐(Market Regime) 통합: SPY/KOSPI 추세를 품질 점수에 반영
- 상승장 BUY 시그널의 적중률이 훨씬 높은 점을 활용
- 품질 범위: 0~30 (기존 0~22에서 시장 레짐 +8/-5 추가)
- 시장 레짐은 개별 종목 지표와 독립적 → 진정한 예측력 추가
"""

import os
import pickle
import time
import math
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_MODEL_PATH = os.path.join(_DATA_DIR, "lgb_model_20d.pkl")
_MODEL_INFO_PATH = os.path.join(_DATA_DIR, "lgb_model_info.pkl")
_CALIBRATION_PATH = os.path.join(_DATA_DIR, "quality_calibration.pkl")

FEATURE_NAMES = [
    "score", "rsi", "vol_ratio", "mom5", "down_streak",
    "volatility", "bb_width", "rsi_change", "ma20_slope",
    "macd_accel", "trend_20d",
    "ticker_rolling_hit_rate", "ticker_rolling_avg_return",
    "ticker_signal_count", "ticker_recent_hit_rate",
    "quality_score", "risk_flags",
    "rsi_vol_interaction", "trend_quality", "score_volatility_adj",
    "bb_rsi_squeeze", "mean_reversion_signal",
    # v6: 시장 레짐 피처
    "market_trend_20d", "market_above_ma20", "market_above_ma50",
    "market_above_ma200", "market_volatility", "market_breadth",
]

_model = None
_model_info = None
_calibration = None
_market_regime_cache: dict[str, dict] = {}  # date_str → regime features


# ============================================================
# 시장 레짐 (Market Regime)
# ============================================================

def _build_market_regime_lookup() -> dict[str, dict]:
    """SPY + KOSPI 10년 데이터 → 날짜별 시장 레짐 dict."""
    from services.cache_service import get_cached_history, set_cached_history
    import yfinance as yf

    global _market_regime_cache
    if _market_regime_cache:
        return _market_regime_cache

    regime = {}

    for idx_ticker, prefix in [("SPY", "us"), ("^KS11", "kr")]:
        try:
            df = get_cached_history(idx_ticker, "10y", "1d")
            if df is None:
                stock = yf.Ticker(idx_ticker)
                df = stock.history(period="10y", interval="1d")
                if not df.empty:
                    set_cached_history(idx_ticker, "10y", "1d", df)
            if df is None or df.empty or len(df) < 220:
                continue

            close = df["Close"].astype(float)
            ma20 = close.rolling(20).mean()
            ma50 = close.rolling(50).mean()
            ma200 = close.rolling(200).mean()
            std20 = close.rolling(20).std()

            for i in range(200, len(df)):
                dt = df.index[i]
                date_key = dt.strftime("%Y-%m-%d")

                c = float(close.iloc[i])
                m20 = float(ma20.iloc[i])
                m50 = float(ma50.iloc[i])
                m200 = float(ma200.iloc[i])
                s20 = float(std20.iloc[i])
                c20 = float(close.iloc[i - 20])

                trend = (c - c20) / c20 * 100 if c20 > 0 else 0
                vol = s20 / c * 100 if c > 0 else 5
                a20 = 1 if c > m20 else 0
                a50 = 1 if c > m50 else 0
                a200 = 1 if c > m200 else 0

                if date_key not in regime:
                    regime[date_key] = {}
                regime[date_key][f"{prefix}_trend"] = round(trend, 2)
                regime[date_key][f"{prefix}_a20"] = a20
                regime[date_key][f"{prefix}_a50"] = a50
                regime[date_key][f"{prefix}_a200"] = a200
                regime[date_key][f"{prefix}_vol"] = round(vol, 2)
                regime[date_key][f"{prefix}_breadth"] = a20 + a50 + a200

        except Exception as e:
            logger.warning(f"시장 인덱스 {idx_ticker} 로드 실패: {e}")

    _market_regime_cache = regime
    logger.info(f"시장 레짐 데이터: {len(regime)}일")
    return regime


def _get_market_features(date_str: str, is_korean: bool = False) -> dict:
    """특정 날짜의 시장 레짐 피처 반환."""
    regime = _market_regime_cache.get(date_str, {})
    p = "kr" if is_korean else "us"

    return {
        "market_trend_20d": regime.get(f"{p}_trend", 0.0),
        "market_above_ma20": regime.get(f"{p}_a20", 0),
        "market_above_ma50": regime.get(f"{p}_a50", 0),
        "market_above_ma200": regime.get(f"{p}_a200", 0),
        "market_volatility": regime.get(f"{p}_vol", 3.0),
        "market_breadth": regime.get(f"{p}_breadth", 1.5),
    }


def get_current_market_features(is_korean: bool = False) -> dict:
    """현재 시장 레짐 (라이브 예측용)."""
    from services.cache_service import get_cached_history, set_cached_history
    import yfinance as yf

    idx = "^KS11" if is_korean else "SPY"
    try:
        df = get_cached_history(idx, "6mo", "1d")
        if df is None:
            stock = yf.Ticker(idx)
            df = stock.history(period="6mo", interval="1d")
            if not df.empty:
                set_cached_history(idx, "6mo", "1d", df)
        if df is None or df.empty or len(df) < 50:
            return {
                "market_trend_20d": 0, "market_above_ma20": 0,
                "market_above_ma50": 0, "market_above_ma200": 0,
                "market_volatility": 3, "market_breadth": 1.5,
            }

        close = df["Close"].astype(float)
        c = float(close.iloc[-1])
        m20 = float(close.rolling(20).mean().iloc[-1])
        m50 = float(close.rolling(50).mean().iloc[-1])
        # 6mo 데이터라 200MA 없을 수 있음
        m200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else m50
        s20 = float(close.rolling(20).std().iloc[-1])
        c20 = float(close.iloc[-21]) if len(close) >= 21 else c

        trend = (c - c20) / c20 * 100 if c20 > 0 else 0
        vol = s20 / c * 100 if c > 0 else 3
        a20 = 1 if c > m20 else 0
        a50 = 1 if c > m50 else 0
        a200 = 1 if c > m200 else 0

        return {
            "market_trend_20d": round(trend, 2),
            "market_above_ma20": a20,
            "market_above_ma50": a50,
            "market_above_ma200": a200,
            "market_volatility": round(vol, 2),
            "market_breadth": a20 + a50 + a200,
        }
    except Exception:
        return {
            "market_trend_20d": 0, "market_above_ma20": 0,
            "market_above_ma50": 0, "market_above_ma200": 0,
            "market_volatility": 3, "market_breadth": 1.5,
        }


# ============================================================
# 품질 점수 + 위험 플래그
# ============================================================

def _signal_quality_score(s: dict) -> int:
    """
    BUY 시그널 품질 점수 (0~30).
    v6: 시장 레짐 추가 (최대 +8/-5).
    """
    q = 0

    # === 시장 레짐 (최대 +8, 최소 -5) — 독립적 예측 변수 ===
    mkt_breadth = s.get("market_breadth", 1.5)
    mkt_trend = s.get("market_trend_20d", 0)
    mkt_vol = s.get("market_volatility", 3)

    # 시장 MA 위치 (0~3 → 점수)
    if mkt_breadth >= 3:
        q += 3  # 강한 상승장: 모든 MA 위
    elif mkt_breadth >= 2:
        q += 2
    elif mkt_breadth >= 1:
        q += 1
    elif mkt_breadth == 0:
        q -= 3  # 하락장: 모든 MA 아래

    # 시장 모멘텀
    if mkt_trend > 5:
        q += 2
    elif mkt_trend > 2:
        q += 1
    elif mkt_trend < -8:
        q -= 2  # 시장 급락

    # 시장 안정성
    if mkt_vol < 1.0:
        q += 2  # 매우 안정
    elif mkt_vol < 1.5:
        q += 1
    elif mkt_vol > 3.5:
        q -= 1  # 불안정

    # 시장 역행 강도: 시장이 조정인데 종목이 강한 BUY → 상대 강도
    if mkt_trend < -2 and s.get("score", 0) >= 8:
        q += 1

    # === 종목 과거 성과 (최대 +6) ===
    t_hit = s.get("ticker_rolling_hit_rate", 50)
    t_cnt = s.get("ticker_signal_count", 0)
    t_recent = s.get("ticker_recent_hit_rate", 50)

    if t_cnt >= 10:
        if t_hit >= 70: q += 5
        elif t_hit >= 65: q += 3
        elif t_hit >= 60: q += 2
        elif t_hit >= 55: q += 1
    elif t_cnt >= 5:
        if t_hit >= 65: q += 2
        elif t_hit >= 60: q += 1

    if t_recent >= 70 and t_cnt >= 5:
        q += 1

    # === 원점수 (최대 +4) ===
    score = s.get("score", 5)
    if score >= 12: q += 4
    elif score >= 10: q += 3
    elif score >= 8: q += 2
    elif score >= 6: q += 1

    # === 변동성 (최대 +3, 최소 -2) ===
    vol = s.get("volatility") or 5
    if vol < 2: q += 3
    elif vol < 2.5: q += 2
    elif vol < 3.5: q += 1
    elif vol > 5: q -= 2
    elif vol > 4: q -= 1

    # === RSI 과매도 (최대 +2) ===
    rsi = s.get("rsi", 50)
    if rsi < 25: q += 2
    elif rsi < 35: q += 1

    # === 추세 확인 (최대 +3, 최소 -1) ===
    macd = s.get("macd_accel") or 0
    slope = s.get("ma20_slope") or 0
    trend = s.get("trend_20d") or 0

    if macd > 0 and slope > 0:
        q += 2
    elif macd > 0.1:
        q += 1

    if -5 <= trend < 0:
        q += 1  # 건전한 조정 후

    if trend < -15:
        q -= 1

    # === 거래량 안정 (최대 +1, 최소 -1) ===
    vr = s.get("vol_ratio", 1)
    if 0.6 <= vr <= 1.5:
        q += 1
    elif vr > 2.5:
        q -= 1

    # === BB 안정 (최대 +1) ===
    bb = s.get("bb_width") or 15
    if bb < 8:
        q += 1

    # === 연구 기반 신호 보너스 (v6.1) ===
    if s.get("rsi_divergence"):
        q += 1
    if s.get("golden_near"):
        q += 1
    if s.get("vol_dry"):
        q += 1

    return max(0, min(35, q))


def _count_risk_flags(s: dict) -> int:
    """위험 플래그 수 (0~8). v6: 시장 위험 추가."""
    flags = 0
    vol = s.get("volatility") or 5
    vr = s.get("vol_ratio", 1)
    mom5 = s.get("mom5", 0)
    rsi = s.get("rsi", 50)
    trend = s.get("trend_20d") or 0
    bb = s.get("bb_width") or 15

    if vol > 5: flags += 1
    if vr > 2.5: flags += 1
    if mom5 > 8: flags += 1
    if rsi > 65: flags += 1
    if trend > 15: flags += 1
    if bb > 20: flags += 1

    # 시장 위험
    mkt_breadth = s.get("market_breadth", 1.5)
    mkt_trend = s.get("market_trend_20d", 0)
    if mkt_breadth == 0 and mkt_trend < -3:
        flags += 1  # 하락장
    if mkt_trend < -8:
        flags += 1  # 시장 급락

    return flags


# ============================================================
# 피처 추출 + 모델
# ============================================================

def _extract_features(s: dict) -> dict:
    score = s.get("score", 0)
    rsi = s.get("rsi", 50)
    vol_ratio = s.get("vol_ratio", 1.0)
    mom5 = s.get("mom5", 0)
    down_streak = s.get("down_streak", 0)
    volatility = s.get("volatility") or 3.0
    bb_width = s.get("bb_width") or 10.0
    rsi_change = s.get("rsi_change") or 0
    ma20_slope = s.get("ma20_slope") or 0
    macd_accel = s.get("macd_accel") or 0
    trend_20d = s.get("trend_20d") or 0
    t_hit = s.get("ticker_rolling_hit_rate", 55.0)
    t_ret = s.get("ticker_rolling_avg_return", 1.0)
    t_cnt = s.get("ticker_signal_count", 0)
    t_recent = s.get("ticker_recent_hit_rate", 55.0)

    quality = _signal_quality_score(s)
    risk = _count_risk_flags(s)

    # 시장 레짐
    mkt_trend = s.get("market_trend_20d", 0)
    mkt_a20 = s.get("market_above_ma20", 0)
    mkt_a50 = s.get("market_above_ma50", 0)
    mkt_a200 = s.get("market_above_ma200", 0)
    mkt_vol = s.get("market_volatility", 3.0)
    mkt_breadth = s.get("market_breadth", 1.5)

    return {
        "score": score, "rsi": rsi, "vol_ratio": vol_ratio,
        "mom5": mom5, "down_streak": down_streak, "volatility": volatility,
        "bb_width": bb_width, "rsi_change": rsi_change, "ma20_slope": ma20_slope,
        "macd_accel": macd_accel, "trend_20d": trend_20d,
        "ticker_rolling_hit_rate": t_hit, "ticker_rolling_avg_return": t_ret,
        "ticker_signal_count": min(t_cnt, 100), "ticker_recent_hit_rate": t_recent,
        "quality_score": quality, "risk_flags": risk,
        "rsi_vol_interaction": (50 - rsi) * (1 / max(volatility, 0.5)),
        "trend_quality": trend_20d * ma20_slope,
        "score_volatility_adj": score / max(volatility, 0.5),
        "bb_rsi_squeeze": (100 - rsi) / 100 * (20 / max(bb_width, 1)),
        "mean_reversion_signal": (50 - rsi) / 50 * (-trend_20d / 10) if trend_20d < 0 else 0,
        # 시장 레짐
        "market_trend_20d": mkt_trend,
        "market_above_ma20": mkt_a20,
        "market_above_ma50": mkt_a50,
        "market_above_ma200": mkt_a200,
        "market_volatility": mkt_vol,
        "market_breadth": mkt_breadth,
    }


def _load_model():
    global _model, _model_info, _calibration
    if _model is not None:
        return _model
    for path, name in [(_MODEL_PATH, "_model"), (_MODEL_INFO_PATH, "_model_info"), (_CALIBRATION_PATH, "_calibration")]:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    globals()[name] = pickle.load(f)
            except Exception:
                pass
    _model = globals().get("_model")
    _model_info = globals().get("_model_info")
    _calibration = globals().get("_calibration")
    return _model


def predict_confidence(features: dict) -> int | None:
    """
    하이브리드 확신도 예측.
    품질 점수 + 위험 필터 + ML + 캘리브레이션 테이블.
    v6: 시장 레짐 자동 통합.
    """
    _load_model()

    # 시장 레짐 피처가 없으면 현재 시장 데이터로 보충
    if "market_breadth" not in features or features.get("market_breadth") is None:
        is_kr = features.get("ticker", "").endswith((".KS", ".KQ"))
        mkt = get_current_market_features(is_kr)
        features = {**features, **mkt}

    quality = _signal_quality_score(features)
    risk = _count_risk_flags(features)

    # 위험 필터: risk >= 2면 패스
    if risk >= 2:
        return None

    # 캘리브레이션 테이블 조회
    cal = _calibration or {}
    net_score = quality - risk

    cal_hit = cal.get(net_score)
    if cal_hit is not None and cal_hit >= 55:
        ml_adj = 0
        if _model is not None:
            try:
                feat = _extract_features(features)
                row = [float(feat.get(n, 0)) for n in FEATURE_NAMES]
                prob = _model.predict(np.array([row]))[0]
                ml_adj = int((prob - 0.5) * 20)
            except Exception:
                pass

        confidence = int(cal_hit + ml_adj)
        return min(95, max(30, confidence))

    return None


# ============================================================
# 모델 학습
# ============================================================

def train_model(hold_days: int = 20) -> dict:
    """
    v6: 시장 레짐 통합 + 3중 필터링 + 캘리브레이션 + LightGBM.
    """
    try:
        import lightgbm as lgb
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return {"error": "lightgbm/scikit-learn 미설치"}

    from services.backtest_service import _precompute_indicators, _score_at
    from services.recommendation_service import DEFAULT_TICKERS
    from services.cache_service import get_cached_history, set_cached_history
    import yfinance as yf

    logger.info(f"ML v6 학습 시작 (hold_days={hold_days})")
    start_time = time.time()

    # === 0. 시장 레짐 데이터 로드 ===
    _build_market_regime_lookup()
    logger.info(f"시장 레짐 로드 완료 ({len(_market_regime_cache)}일)")

    # === 1. 데이터 수집 ===
    ticker_signals: dict[str, list] = {}
    sample_interval = 3

    for ticker in DEFAULT_TICKERS:
        try:
            df = get_cached_history(ticker, "10y", "1d")
            if df is None:
                stock = yf.Ticker(ticker)
                df = stock.history(period="10y", interval="1d")
                if not df.empty:
                    set_cached_history(ticker, "10y", "1d", df)
            if df is None or df.empty or len(df) < 220:
                continue

            close = df["Close"]
            volume = df["Volume"]
            ind = _precompute_indicators(close, volume)
            is_korean = ticker.endswith((".KS", ".KQ"))
            sigs = []

            close_arr = close.values.astype(float)

            for i in range(200, len(df) - hold_days, sample_interval):
                signals = _score_at(ind, i)
                if signals is None or signals["score"] < 5:
                    continue

                entry = signals["price"]
                exit_p = float(close_arr[i + hold_days])
                ret = (exit_p - entry) / entry * 100
                target = 1 if ret > 0 else 0

                # 기간 내 최대 수익 (수익 기회 측정)
                window = close_arr[i + 1: i + hold_days + 1]
                max_price = float(np.max(window))
                max_ret = (max_price - entry) / entry * 100
                target_opp = 1 if max_ret > 1.0 else 0  # 1%+ 수익 기회

                # 시장 레짐 추가
                date_str = df.index[i].strftime("%Y-%m-%d")
                mkt = _get_market_features(date_str, is_korean)
                signals.update(mkt)

                sigs.append((i, signals, ret, target, max_ret, target_opp))

            if sigs:
                ticker_signals[ticker] = sigs
        except Exception:
            continue

    # 워크포워드 종목 성과
    all_rows = []
    for ticker, sigs in ticker_signals.items():
        past_t = []
        past_r = []

        for date_i, signals, ret, target, max_ret, target_opp in sigs:
            if len(past_t) >= 3:
                rh = sum(past_t) / len(past_t) * 100
                rr = sum(past_r) / len(past_r)
            else:
                rh, rr = 55.0, 1.0

            recent = past_t[-10:] if len(past_t) >= 3 else past_t
            rec_h = sum(recent) / len(recent) * 100 if recent else 55.0

            enriched = dict(signals)
            enriched["ticker_rolling_hit_rate"] = rh
            enriched["ticker_rolling_avg_return"] = rr
            enriched["ticker_signal_count"] = len(past_t)
            enriched["ticker_recent_hit_rate"] = rec_h

            feat = _extract_features(enriched)
            feat["target"] = target
            feat["target_opp"] = target_opp  # 수익 기회 타겟
            feat["max_return"] = max_ret
            feat["return"] = ret
            feat["date_idx"] = date_i
            all_rows.append(feat)

            past_t.append(target)
            past_r.append(ret)

    if len(all_rows) < 200:
        return {"error": f"데이터 부족: {len(all_rows)}건"}

    df_all = pd.DataFrame(all_rows)
    logger.info(f"데이터: {len(df_all)}건")

    # 시간순 분할
    df_all = df_all.sort_values("date_idx")
    split_idx = int(len(df_all) * 0.7)
    train_df = df_all.iloc[:split_idx]
    test_df = df_all.iloc[split_idx:]

    y_train = train_df["target"].values
    y_test = test_df["target"].values
    y_test_opp = test_df["target_opp"].values  # 수익 기회 타겟
    test_ret = test_df["return"].values
    test_max_ret = test_df["max_return"].values
    test_quality = test_df["quality_score"].values
    test_risk = test_df["risk_flags"].values

    # === 2. 캘리브레이션 테이블 (수익 기회 기반) ===
    train_quality = train_df["quality_score"].values
    train_risk = train_df["risk_flags"].values
    train_net = train_quality - train_risk
    y_train_opp = train_df["target_opp"].values

    calibration = {}
    cal_end = {}  # 종료시 적중률도 별도 보관
    for ns in range(0, 31):
        mask = train_net == ns
        if mask.sum() >= 10:
            calibration[ns] = round(y_train_opp[mask].mean() * 100, 1)
            cal_end[ns] = round(y_train[mask].mean() * 100, 1)

    for ns in range(0, 31):
        if ns not in calibration:
            neighbors = [calibration.get(ns - 1), calibration.get(ns + 1)]
            neighbors = [n for n in neighbors if n is not None]
            if neighbors:
                calibration[ns] = round(sum(neighbors) / len(neighbors), 1)

    logger.info(f"수익기회 캘리브레이션: {calibration}")

    # === 3. LightGBM 학습 ===
    X_train = train_df[FEATURE_NAMES].values
    X_test = test_df[FEATURE_NAMES].values

    positions = np.linspace(0, 1, len(X_train))
    weights = 0.3 + 0.7 * np.power(positions, 2.0)

    params = {
        "objective": "binary", "metric": "auc", "verbose": -1, "seed": 42,
        "num_leaves": 20, "max_depth": 5, "min_child_samples": 30,
        "learning_rate": 0.02, "subsample": 0.75, "colsample_bytree": 0.65,
        "reg_alpha": 1.0, "reg_lambda": 2.0, "is_unbalance": True,
    }

    lgb_train = lgb.Dataset(X_train, y_train, weight=weights, feature_name=FEATURE_NAMES)
    lgb_val = lgb.Dataset(X_test, y_test, feature_name=FEATURE_NAMES, reference=lgb_train)
    callbacks = [lgb.early_stopping(30, verbose=False), lgb.log_evaluation(0)]

    lgb_model = lgb.train(params, lgb_train, num_boost_round=1000,
                          valid_sets=[lgb_val], callbacks=callbacks)
    ml_probs = lgb_model.predict(X_test)
    try:
        auc = roc_auc_score(y_test, ml_probs)
    except ValueError:
        auc = 0.5

    # === 4. 테스트셋 분석 ===
    test_net = test_quality - test_risk

    # 4a. 시장 레짐별 적중률 (핵심 분석)
    test_mkt_breadth = test_df["market_breadth"].values
    test_mkt_trend = test_df["market_trend_20d"].values

    market_analysis = []
    for regime_name, regime_mask in [
        ("상승장(breadth>=3)", test_mkt_breadth >= 3),
        ("보통장(breadth==2)", test_mkt_breadth == 2),
        ("약세장(breadth<=1)", test_mkt_breadth <= 1),
        ("하락장(breadth==0)", test_mkt_breadth == 0),
        ("시장모멘텀>3%", test_mkt_trend > 3),
        ("시장모멘텀<-3%", test_mkt_trend < -3),
    ]:
        n = regime_mask.sum()
        if n >= 10:
            hit = y_test[regime_mask].mean() * 100
            avg_r = test_ret[regime_mask].mean()
            market_analysis.append({
                "regime": regime_name,
                "hit_rate": round(hit, 1),
                "count": int(n),
                "avg_return": round(avg_r, 2),
            })

    # 시장 레짐 + 품질 교차 분석
    cross_analysis = []
    for min_q in [6, 8, 10, 12]:
        for regime_name, regime_mask in [
            ("상승장", test_mkt_breadth >= 3),
            ("보통장", (test_mkt_breadth >= 1) & (test_mkt_breadth < 3)),
            ("하락장", test_mkt_breadth == 0),
        ]:
            mask = (test_quality >= min_q) & regime_mask & (test_risk <= 1)
            n = mask.sum()
            if n >= 5:
                hit = y_test[mask].mean() * 100
                avg_r = test_ret[mask].mean()
                cross_analysis.append({
                    "min_quality": min_q,
                    "market": regime_name,
                    "hit_rate": round(hit, 1),
                    "count": int(n),
                    "avg_return": round(avg_r, 2),
                })

    # 4b. 품질 점수별 적중률
    quality_analysis = []
    for min_q in range(0, 25):
        mask = test_quality >= min_q
        n = mask.sum()
        if n < 5:
            continue
        hit = y_test[mask].mean() * 100
        avg_r = test_ret[mask].mean()
        quality_analysis.append({
            "min_quality": min_q, "hit_rate": round(hit, 1),
            "count": int(n), "coverage": round(n / len(y_test) * 100, 1),
            "avg_return": round(avg_r, 2),
        })

    # 4c. 품질 + 위험필터 조합
    filtered_analysis = []
    for min_q in range(0, 22):
        for max_risk in [0, 1]:
            mask = (test_quality >= min_q) & (test_risk <= max_risk)
            n = mask.sum()
            if n < 5:
                continue
            hit = y_test[mask].mean() * 100
            avg_r = test_ret[mask].mean()
            filtered_analysis.append({
                "min_quality": min_q, "max_risk": max_risk,
                "hit_rate": round(hit, 1), "count": int(n),
                "coverage": round(n / len(y_test) * 100, 1),
                "avg_return": round(avg_r, 2),
            })

    # 4d. 넷스코어별
    net_analysis = []
    for min_net in range(0, 25):
        mask = test_net >= min_net
        n = mask.sum()
        if n < 5:
            continue
        hit = y_test[mask].mean() * 100
        avg_r = test_ret[mask].mean()
        net_analysis.append({
            "min_net_score": min_net, "hit_rate": round(hit, 1),
            "count": int(n), "coverage": round(n / len(y_test) * 100, 1),
            "avg_return": round(avg_r, 2),
        })

    # 4e. 앙상블: 품질 + risk=0 + ML >= 0.50
    ensemble_analysis = []
    for min_q in range(4, 22):
        mask = (test_quality >= min_q) & (test_risk == 0) & (ml_probs >= 0.50)
        n = mask.sum()
        if n < 5:
            continue
        hit = y_test[mask].mean() * 100
        avg_r = test_ret[mask].mean()
        ensemble_analysis.append({
            "min_quality": min_q, "hit_rate": round(hit, 1),
            "count": int(n), "coverage": round(n / len(y_test) * 100, 1),
            "avg_return": round(avg_r, 2),
        })

    # 4f. ★ 수익 기회 분석 (target_opp: 20일내 1%+ 수익 기회 있었는가?)
    opp_analysis = []
    for min_q in range(0, 25):
        for max_risk in [0, 1, 99]:  # 99 = no filter
            if max_risk == 99:
                mask = test_quality >= min_q
            else:
                mask = (test_quality >= min_q) & (test_risk <= max_risk)
            n = mask.sum()
            if n < 5:
                continue
            opp_hit = y_test_opp[mask].mean() * 100
            end_hit = y_test[mask].mean() * 100
            avg_max = test_max_ret[mask].mean()
            opp_analysis.append({
                "min_quality": min_q,
                "max_risk": max_risk if max_risk != 99 else "any",
                "opportunity_rate": round(opp_hit, 1),
                "end_hit_rate": round(end_hit, 1),
                "count": int(n),
                "avg_max_return": round(avg_max, 2),
            })

    # 수익 기회 80%+ 필터
    opp_80 = sorted(
        [o for o in opp_analysis if o["opportunity_rate"] >= 80 and o["count"] >= 10],
        key=lambda x: (-x["count"])
    )

    # 전체 수익 기회 베이스라인
    opp_baseline = round(y_test_opp.mean() * 100, 1)
    avg_max_baseline = round(test_max_ret.mean(), 2)

    # 최고 적중률 찾기
    all_combos = filtered_analysis + ensemble_analysis + cross_analysis
    best_80 = sorted([e for e in all_combos if e.get("hit_rate", 0) >= 80 and e.get("count", 0) >= 5],
                     key=lambda x: -x.get("count", 0))
    best_75 = sorted([e for e in all_combos if e.get("hit_rate", 0) >= 75 and e.get("count", 0) >= 5],
                     key=lambda x: -x.get("count", 0))
    best_70 = sorted([e for e in all_combos if e.get("hit_rate", 0) >= 70 and e.get("count", 0) >= 5],
                     key=lambda x: -x.get("count", 0))

    # 피처 중요도
    importance = dict(zip(FEATURE_NAMES, [int(x) for x in lgb_model.feature_importance()]))
    importance_sorted = dict(sorted(importance.items(), key=lambda x: -x[1]))

    # === 5. 저장 ===
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_MODEL_PATH, "wb") as f:
        pickle.dump(lgb_model, f)
    with open(_CALIBRATION_PATH, "wb") as f:
        pickle.dump(calibration, f)

    info = {
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hold_days": hold_days,
        "train_size": len(train_df),
        "test_size": len(test_df),
        "total_samples": len(df_all),
        "auc": round(auc, 4),
        "calibration_table": calibration,
        "market_regime_analysis": market_analysis,
        "market_quality_cross": cross_analysis,
        "quality_analysis": quality_analysis,
        "filtered_analysis": filtered_analysis,
        "net_score_analysis": net_analysis,
        "ensemble_analysis": ensemble_analysis,
        "opportunity_baseline": opp_baseline,
        "avg_max_return_baseline": avg_max_baseline,
        "opportunity_80_plus": opp_80[:10],
        "opportunity_analysis_top": [o for o in opp_analysis
                                     if o["min_quality"] >= 8 and o.get("max_risk") == 0][:15],
        "best_80_pct": best_80[:5],
        "best_75_pct": best_75[:5],
        "best_70_pct": best_70[:5],
        "feature_importance": importance_sorted,
        "train_duration_sec": round(time.time() - start_time, 1),
        "positive_ratio_train": round(y_train.mean() * 100, 1),
        "positive_ratio_test": round(y_test.mean() * 100, 1),
    }

    with open(_MODEL_INFO_PATH, "wb") as f:
        pickle.dump(info, f)

    global _model, _model_info, _calibration
    _model = lgb_model
    _model_info = info
    _calibration = calibration

    logger.info(f"v6 완료: AUC={auc:.4f}, 80%+ {len(best_80)}개, 75%+ {len(best_75)}개")
    return info


def get_model_info() -> dict | None:
    global _model_info
    if _model_info is not None:
        return _model_info
    if os.path.exists(_MODEL_INFO_PATH):
        try:
            with open(_MODEL_INFO_PATH, "rb") as f:
                _model_info = pickle.load(f)
            return _model_info
        except Exception:
            pass
    return None


def reload_model():
    global _model, _model_info, _calibration, _market_regime_cache
    _model = None
    _model_info = None
    _calibration = None
    _market_regime_cache = {}
    _load_model()
