import yfinance as yf
import pandas as pd
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
    stock = yf.Ticker(ticker)
    df = stock.history(period="1y", interval="1d")

    if df.empty or len(df) < 20:
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
