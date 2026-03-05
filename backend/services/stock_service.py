import yfinance as yf
from typing import Optional
from services.kr_stocks import search_kr_stocks


def search_stocks(query: str) -> list[dict]:
    """Search for stocks by name or ticker."""
    # yfinance doesn't have a direct search API, so we try common patterns
    results = []

    # Try Korean stock name search first
    kr_results = search_kr_stocks(query)
    if kr_results:
        return kr_results

    # Try as direct ticker
    try:
        ticker = yf.Ticker(query.upper())
        info = ticker.fast_info
        history = ticker.history(period="1d")
        if not history.empty:
            results.append({
                "ticker": query.upper(),
                "name": getattr(info, "company_name", query.upper()),
                "exchange": getattr(info, "exchange", ""),
                "currency": getattr(info, "currency", "USD"),
            })
    except Exception:
        pass

    # Try Korean stock suffixes
    if not results and query.isdigit():
        for suffix in [".KS", ".KQ"]:
            try:
                t = query + suffix
                ticker = yf.Ticker(t)
                history = ticker.history(period="1d")
                if not history.empty:
                    info = ticker.fast_info
                    results.append({
                        "ticker": t,
                        "name": getattr(info, "company_name", t),
                        "exchange": "KOSPI" if suffix == ".KS" else "KOSDAQ",
                        "currency": "KRW",
                    })
            except Exception:
                pass

    return results


def get_quote(ticker: str) -> dict:
    """Get current price and daily change for a ticker."""
    stock = yf.Ticker(ticker)
    info = stock.fast_info

    try:
        current_price = info.last_price
        previous_close = info.previous_close
        if current_price and previous_close and previous_close != 0:
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100
        else:
            change = 0.0
            change_percent = 0.0
    except Exception:
        current_price = None
        change = 0.0
        change_percent = 0.0

    history = stock.history(period="1d", interval="1m")

    # Get company name from full info
    name = ticker
    try:
        full_info = stock.info
        name = full_info.get("shortName") or full_info.get("longName") or ticker
    except Exception:
        pass

    return {
        "ticker": ticker,
        "name": name,
        "current_price": current_price,
        "previous_close": getattr(info, "previous_close", None),
        "change": round(change, 4) if change else 0,
        "change_percent": round(change_percent, 2) if change_percent else 0,
        "volume": getattr(info, "three_month_average_volume", None),
        "market_cap": getattr(info, "market_cap", None),
        "currency": getattr(info, "currency", "USD"),
        "52_week_high": getattr(info, "year_high", None),
        "52_week_low": getattr(info, "year_low", None),
    }


def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> list[dict]:
    """Get historical price data."""
    stock = yf.Ticker(ticker)
    history = stock.history(period=period, interval=interval)

    if history.empty:
        return []

    result = []
    for date, row in history.iterrows():
        result.append({
            "date": date.strftime("%Y-%m-%d"),
            "open": round(float(row["Open"]), 4),
            "high": round(float(row["High"]), 4),
            "low": round(float(row["Low"]), 4),
            "close": round(float(row["Close"]), 4),
            "volume": int(row["Volume"]),
        })

    return result
