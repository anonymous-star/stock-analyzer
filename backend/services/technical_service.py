import yfinance as yf
import pandas as pd
from services.cache_service import get_cached_history, set_cached_history
try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False


def _safe_float(val) -> float | None:
    try:
        if val is None or (hasattr(val, '__class__') and val.__class__.__name__ == 'float' and str(val) == 'nan'):
            return None
        f = float(val)
        import math
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def get_technical_indicators(ticker: str) -> dict:
    """Calculate technical indicators for a ticker."""
    # 캐시 우선
    df = get_cached_history(ticker, "1y", "1d")
    if df is None:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="1y", interval="1d")
        except Exception:
            df = None
        # yfinance 실패 시 curl_cffi 폴백
        if df is None or df.empty:
            try:
                from services.stock_service import _fetch_history_cffi
                df = _fetch_history_cffi(ticker, "1y", "1d")
            except Exception:
                df = None
        if df is not None and not df.empty:
            set_cached_history(ticker, "1y", "1d", df)

    if df is None or df.empty or len(df) < 20:
        return {"error": "Insufficient data for technical analysis"}

    df = df.copy()
    close = df["Close"]
    volume = df["Volume"]

    result = {
        "ticker": ticker,
        "last_updated": df.index[-1].strftime("%Y-%m-%d"),
        "current_price": _safe_float(close.iloc[-1]),
    }

    # Moving Averages
    for period in [20, 50, 200]:
        if len(df) >= period:
            ma = close.rolling(window=period).mean()
            result[f"ma{period}"] = _safe_float(ma.iloc[-1])
        else:
            result[f"ma{period}"] = None

    if HAS_PANDAS_TA:
        # RSI
        rsi = ta.rsi(close, length=14)
        if rsi is not None and not rsi.empty:
            result["rsi"] = _safe_float(rsi.iloc[-1])
        else:
            result["rsi"] = None

        # MACD
        macd_df = ta.macd(close, fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            result["macd"] = {
                "macd": _safe_float(macd_df.iloc[-1, 0]),
                "signal": _safe_float(macd_df.iloc[-1, 2]),
                "histogram": _safe_float(macd_df.iloc[-1, 1]),
            }
        else:
            result["macd"] = None

        # Bollinger Bands
        bb = ta.bbands(close, length=20, std=2)
        if bb is not None and not bb.empty:
            result["bollinger_bands"] = {
                "upper": _safe_float(bb.iloc[-1, 0]),
                "mid": _safe_float(bb.iloc[-1, 1]),
                "lower": _safe_float(bb.iloc[-1, 2]),
            }
        else:
            result["bollinger_bands"] = None
    else:
        # Fallback manual calculations
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean()
        avg_loss = loss.rolling(window=14).mean()
        rs = avg_gain / avg_loss
        rsi_series = 100 - (100 / (1 + rs))
        result["rsi"] = _safe_float(rsi_series.iloc[-1])

        # MACD
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        result["macd"] = {
            "macd": _safe_float(macd_line.iloc[-1]),
            "signal": _safe_float(signal_line.iloc[-1]),
            "histogram": _safe_float(histogram.iloc[-1]),
        }

        # Bollinger Bands
        ma20 = close.rolling(window=20).mean()
        std20 = close.rolling(window=20).std()
        result["bollinger_bands"] = {
            "upper": _safe_float((ma20 + 2 * std20).iloc[-1]),
            "mid": _safe_float(ma20.iloc[-1]),
            "lower": _safe_float((ma20 - 2 * std20).iloc[-1]),
        }

    # Volume MA
    vol_ma20 = volume.rolling(window=20).mean()
    result["volume_ma20"] = _safe_float(vol_ma20.iloc[-1])
    result["current_volume"] = int(volume.iloc[-1]) if not pd.isna(volume.iloc[-1]) else None

    # Momentum metrics
    if len(close) >= 6:
        mom5 = (float(close.iloc[-1]) - float(close.iloc[-6])) / float(close.iloc[-6]) * 100
        result["momentum_5d"] = round(mom5, 2)
    if len(close) >= 11:
        mom10 = (float(close.iloc[-1]) - float(close.iloc[-11])) / float(close.iloc[-11]) * 100
        result["momentum_10d"] = round(mom10, 2)

    # Consecutive down days
    down_streak = 0
    for j in range(len(close) - 1, max(len(close) - 11, 0), -1):
        if float(close.iloc[j]) < float(close.iloc[j - 1]):
            down_streak += 1
        else:
            break
    result["down_streak"] = down_streak

    # Volatility (20-day std / price, %)
    if len(close) >= 20:
        vol_20d = float(close.tail(20).std() / close.iloc[-1] * 100)
        result["volatility"] = round(vol_20d, 2)

    # MACD acceleration (histogram change)
    macd_data = result.get("macd")
    if macd_data and macd_data.get("histogram") is not None and len(close) >= 30:
        try:
            if HAS_PANDAS_TA:
                macd_df = ta.macd(close, fast=12, slow=26, signal=9)
                if macd_df is not None and len(macd_df) >= 2:
                    hist_now = _safe_float(macd_df.iloc[-1, 1])
                    hist_prev = _safe_float(macd_df.iloc[-2, 1])
                    if hist_now is not None and hist_prev is not None:
                        result["macd_accel"] = round(hist_now - hist_prev, 4)
            else:
                ema12 = close.ewm(span=12, adjust=False).mean()
                ema26 = close.ewm(span=26, adjust=False).mean()
                macd_line = ema12 - ema26
                sig = macd_line.ewm(span=9, adjust=False).mean()
                hist_series = macd_line - sig
                result["macd_accel"] = round(float(hist_series.iloc[-1]) - float(hist_series.iloc[-2]), 4)
        except Exception:
            pass

    # MA20 slope (5-day change %)
    if len(close) >= 25:
        ma20_now = result.get("ma20")
        ma20_prev = _safe_float(close.rolling(20).mean().iloc[-6])
        if ma20_now and ma20_prev and ma20_prev > 0:
            result["ma20_slope"] = round((ma20_now - ma20_prev) / ma20_prev * 100, 3)

    # BB width (%)
    bb = result.get("bollinger_bands")
    if bb and bb.get("upper") and bb.get("lower") and bb.get("mid") and bb["mid"] > 0:
        result["bb_width"] = round((bb["upper"] - bb["lower"]) / bb["mid"] * 100, 2)

    # RSI change (5-day)
    rsi_now = result.get("rsi")
    if rsi_now is not None and len(close) >= 20:
        try:
            prev_close = close.iloc[:-5]
            if HAS_PANDAS_TA:
                rsi_prev_s = ta.rsi(prev_close, length=14)
                rsi_prev = _safe_float(rsi_prev_s.iloc[-1]) if rsi_prev_s is not None and not rsi_prev_s.empty else None
            else:
                d = prev_close.diff()
                g = d.clip(lower=0).rolling(14).mean()
                l = (-d.clip(upper=0)).rolling(14).mean()
                rs_p = g / l
                rsi_p = 100 - (100 / (1 + rs_p))
                rsi_prev = _safe_float(rsi_p.iloc[-1])
            if rsi_prev is not None:
                result["rsi_change_5d"] = round(rsi_now - rsi_prev, 1)
        except Exception:
            pass

    # 20-day trend (%)
    if len(close) >= 21:
        price_20d_ago = float(close.iloc[-21])
        if price_20d_ago > 0:
            result["trend_20d"] = round((float(close.iloc[-1]) - price_20d_ago) / price_20d_ago * 100, 2)

    # Signals interpretation
    result["signals"] = _interpret_signals(result)

    return result


def _interpret_signals(data: dict) -> dict:
    signals = {}
    price = data.get("current_price")
    ma20 = data.get("ma20")
    ma50 = data.get("ma50")
    rsi = data.get("rsi")
    macd = data.get("macd")
    bb = data.get("bollinger_bands")

    # MA signal
    if price and ma20 and ma50:
        if price > ma20 > ma50:
            signals["ma_trend"] = "bullish"
        elif price < ma20 < ma50:
            signals["ma_trend"] = "bearish"
        else:
            signals["ma_trend"] = "neutral"

    # RSI signal
    if rsi is not None:
        if rsi > 70:
            signals["rsi_signal"] = "overbought"
        elif rsi < 30:
            signals["rsi_signal"] = "oversold"
        else:
            signals["rsi_signal"] = "neutral"

    # MACD signal
    if macd:
        macd_val = macd.get("macd")
        signal_val = macd.get("signal")
        hist = macd.get("histogram")
        if macd_val is not None and signal_val is not None:
            if macd_val > signal_val:
                signals["macd_signal"] = "bullish"
            else:
                signals["macd_signal"] = "bearish"

    # Bollinger Band position
    if bb and price:
        upper = bb.get("upper")
        lower = bb.get("lower")
        mid = bb.get("mid")
        if upper and lower and mid:
            if price > upper:
                signals["bb_position"] = "above_upper"
            elif price < lower:
                signals["bb_position"] = "below_lower"
            elif price > mid:
                signals["bb_position"] = "upper_half"
            else:
                signals["bb_position"] = "lower_half"

    return signals
