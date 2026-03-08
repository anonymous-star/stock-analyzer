import yfinance as yf
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from services.kr_stocks import search_kr_stocks
from services.cache_service import (
    get_cached_info, set_cached_info,
    get_cached_history, set_cached_history,
)

_search_executor = ThreadPoolExecutor(max_workers=2)

# 미국 주요 종목 매핑 (검색용)
US_STOCKS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "NVIDIA", "AMZN": "Amazon",
    "META": "Meta Platforms", "GOOGL": "Alphabet (Google)", "GOOG": "Alphabet (Google) C",
    "AVGO": "Broadcom", "TSLA": "Tesla", "COST": "Costco", "NFLX": "Netflix",
    "AMD": "AMD", "ADBE": "Adobe", "PEP": "PepsiCo", "QCOM": "Qualcomm",
    "TMUS": "T-Mobile", "CSCO": "Cisco", "INTC": "Intel", "INTU": "Intuit",
    "CMCSA": "Comcast", "TXN": "Texas Instruments", "AMGN": "Amgen",
    "HON": "Honeywell", "AMAT": "Applied Materials", "BKNG": "Booking Holdings",
    "ISRG": "Intuitive Surgical", "LRCX": "Lam Research", "VRTX": "Vertex Pharma",
    "ADI": "Analog Devices", "REGN": "Regeneron", "KLAC": "KLA Corp",
    "PANW": "Palo Alto Networks", "ADP": "ADP", "MDLZ": "Mondelez",
    "SNPS": "Synopsys", "CDNS": "Cadence Design", "GILD": "Gilead Sciences",
    "MELI": "MercadoLibre", "CRWD": "CrowdStrike", "PYPL": "PayPal",
    "MAR": "Marriott", "CTAS": "Cintas", "ABNB": "Airbnb",
    "MRVL": "Marvell Technology", "ORLY": "O'Reilly Auto", "FTNT": "Fortinet",
    "CEG": "Constellation Energy", "DASH": "DoorDash", "WDAY": "Workday",
    "CSX": "CSX Corp", "NXPI": "NXP Semiconductors", "ADSK": "Autodesk",
    "ROP": "Roper Technologies", "FANG": "Diamondback Energy", "MNST": "Monster Beverage",
    "PCAR": "PACCAR", "ROST": "Ross Stores", "AEP": "American Electric Power",
    "PAYX": "Paychex", "FAST": "Fastenal", "KDP": "Keurig Dr Pepper",
    "DDOG": "Datadog", "ODFL": "Old Dominion Freight", "KHC": "Kraft Heinz",
    "EA": "Electronic Arts", "VRSK": "Verisk Analytics", "CPRT": "Copart",
    "GEHC": "GE Healthcare", "EXC": "Exelon", "LULU": "Lululemon",
    "BKR": "Baker Hughes", "XEL": "Xcel Energy", "CTSH": "Cognizant",
    "IDXX": "IDEXX Labs", "CCEP": "Coca-Cola Europacific", "TTD": "The Trade Desk",
    "MCHP": "Microchip Technology", "ON": "ON Semiconductor", "CDW": "CDW Corp",
    "ANSS": "Ansys", "DXCM": "DexCom", "GFS": "GlobalFoundries",
    "ILMN": "Illumina", "WBD": "Warner Bros Discovery", "ZS": "Zscaler",
    "MDB": "MongoDB", "TEAM": "Atlassian", "BIIB": "Biogen",
    "DLTR": "Dollar Tree", "ARM": "Arm Holdings", "SMCI": "Super Micro Computer",
    "APP": "AppLovin", "PLTR": "Palantir", "COIN": "Coinbase",
    "MSTR": "MicroStrategy", "CRSP": "CRISPR Therapeutics",
    "JPM": "JPMorgan Chase", "V": "Visa", "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil", "LLY": "Eli Lilly", "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble", "CRM": "Salesforce", "ORCL": "Oracle",
    "DIS": "Walt Disney", "BA": "Boeing", "NKE": "Nike",
    "SBUX": "Starbucks", "MCD": "McDonald's", "KO": "Coca-Cola",
    "WMT": "Walmart", "HD": "Home Depot", "CAT": "Caterpillar",
    "GS": "Goldman Sachs", "MS": "Morgan Stanley", "SQ": "Block (Square)",
    "SNAP": "Snap Inc", "UBER": "Uber", "LYFT": "Lyft",
    "ROKU": "Roku", "SHOP": "Shopify",
    "RBLX": "Roblox", "SOFI": "SoFi Technologies", "RIVN": "Rivian",
    "LCID": "Lucid Group", "NIO": "NIO", "XPEV": "XPeng",
    "LI": "Li Auto", "BABA": "Alibaba", "JD": "JD.com",
    "PDD": "PDD Holdings (Temu)", "BIDU": "Baidu", "BRK-B": "Berkshire Hathaway",
    "WFC": "Wells Fargo", "C": "Citigroup", "BAC": "Bank of America",
    "T": "AT&T", "VZ": "Verizon", "ABBV": "AbbVie",
    "MRK": "Merck", "PFE": "Pfizer", "TMO": "Thermo Fisher",
    "ABT": "Abbott Labs", "DHR": "Danaher", "BMY": "Bristol-Myers Squibb",
    "COP": "ConocoPhillips", "CVX": "Chevron", "NEE": "NextEra Energy",
    "SO": "Southern Company", "DUK": "Duke Energy",
}


def search_stocks(query: str) -> list[dict]:
    """Search for stocks by name or ticker (partial match supported)."""
    results = []
    query_upper = query.strip().upper()
    query_lower = query.strip().lower()

    # Korean stock name search
    kr_results = search_kr_stocks(query)
    results.extend(kr_results)

    # US stock search: partial match on ticker and name
    seen_tickers = {r["ticker"] for r in results}
    for ticker, name in US_STOCKS.items():
        if ticker in seen_tickers:
            continue
        if (query_upper in ticker or
            query_lower in name.lower() or
            query_lower in ticker.lower()):
            seen_tickers.add(ticker)
            results.append({
                "ticker": ticker,
                "name": name,
                "exchange": "NASDAQ/NYSE",
                "currency": "USD",
            })

    # If no results, try yfinance as fallback (with 5s timeout)
    if not results:
        def _yf_lookup():
            try:
                stock = yf.Ticker(query_upper)
                history = stock.history(period="1d")
                if not history.empty:
                    n = query_upper
                    try:
                        full_info = stock.info
                        n = full_info.get("shortName") or full_info.get("longName") or query_upper
                    except Exception:
                        pass
                    return {"ticker": query_upper, "name": n, "exchange": "", "currency": getattr(stock.fast_info, "currency", "USD")}
            except Exception:
                pass
            return None

        try:
            future = _search_executor.submit(_yf_lookup)
            result = future.result(timeout=5)
            if result:
                results.append(result)
        except (FuturesTimeoutError, Exception):
            pass

    # Try Korean stock code (with 5s timeout)
    if not results and query.strip().isdigit():
        def _kr_lookup():
            found = []
            for suffix in [".KS", ".KQ"]:
                try:
                    t = query.strip() + suffix
                    stock = yf.Ticker(t)
                    history = stock.history(period="1d")
                    if not history.empty:
                        n = t
                        try:
                            full_info = stock.info
                            n = full_info.get("shortName") or full_info.get("longName") or t
                        except Exception:
                            pass
                        found.append({"ticker": t, "name": n, "exchange": "KOSPI" if suffix == ".KS" else "KOSDAQ", "currency": "KRW"})
                except Exception:
                    pass
            return found

        try:
            future = _search_executor.submit(_kr_lookup)
            kr_found = future.result(timeout=5)
            results.extend(kr_found)
        except (FuturesTimeoutError, Exception):
            pass

    return results[:20]


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

    # Get company name + financial data from full info (캐시 우선)
    name = ticker
    financials = {}
    try:
        full_info = get_cached_info(ticker)
        if full_info is None:
            full_info = stock.info
            set_cached_info(ticker, full_info)

        name = full_info.get("shortName") or full_info.get("longName") or ticker
        # 재무 데이터 추출 (추가 API 호출 없음)
        import math

        def _sf(v):
            try:
                if v is None: return None
                f = float(v)
                return None if math.isnan(f) or math.isinf(f) else round(f, 4)
            except (TypeError, ValueError):
                return None

        financials = {
            "pe_ratio": _sf(full_info.get("trailingPE")),
            "forward_pe": _sf(full_info.get("forwardPE")),
            "pb_ratio": _sf(full_info.get("priceToBook")),
            "roe": _sf(full_info.get("returnOnEquity")),
            "debt_to_equity": _sf(full_info.get("debtToEquity")),
            "revenue_growth": _sf(full_info.get("revenueGrowth")),
            "earnings_growth": _sf(full_info.get("earningsGrowth")),
            "profit_margin": _sf(full_info.get("profitMargins")),
        }
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
        "financials": financials,
    }


def get_price_history(ticker: str, period: str = "6mo", interval: str = "1d") -> list[dict]:
    """Get historical price data."""
    # 캐시 우선
    history = get_cached_history(ticker, period, interval)
    if history is None:
        stock = yf.Ticker(ticker)
        history = stock.history(period=period, interval=interval)
        if not history.empty:
            set_cached_history(ticker, period, interval, history)

    if history is None or history.empty:
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
