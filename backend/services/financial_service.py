import yfinance as yf
import math


def _safe_float(val) -> float | None:
    try:
        if val is None:
            return None
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def get_financials(ticker: str) -> dict:
    """Get financial statements and key metrics for a ticker."""
    stock = yf.Ticker(ticker)
    info = stock.info

    result = {
        "ticker": ticker,
        "valuation": {
            "pe_ratio": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "pb_ratio": _safe_float(info.get("priceToBook")),
            "ps_ratio": _safe_float(info.get("priceToSalesTrailing12Months")),
            "peg_ratio": _safe_float(info.get("pegRatio")),
            "ev_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        },
        "profitability": {
            "gross_margin": _safe_float(info.get("grossMargins")),
            "operating_margin": _safe_float(info.get("operatingMargins")),
            "profit_margin": _safe_float(info.get("profitMargins")),
            "roe": _safe_float(info.get("returnOnEquity")),
            "roa": _safe_float(info.get("returnOnAssets")),
        },
        "growth": {
            "revenue_growth": _safe_float(info.get("revenueGrowth")),
            "earnings_growth": _safe_float(info.get("earningsGrowth")),
            "earnings_quarterly_growth": _safe_float(info.get("earningsQuarterlyGrowth")),
        },
        "per_share": {
            "eps_trailing": _safe_float(info.get("trailingEps")),
            "eps_forward": _safe_float(info.get("forwardEps")),
            "book_value": _safe_float(info.get("bookValue")),
            "dividend_rate": _safe_float(info.get("dividendRate")),
            "dividend_yield": _safe_float(info.get("dividendYield")),
        },
        "balance_sheet": {
            "total_cash": _safe_int(info.get("totalCash")),
            "total_debt": _safe_int(info.get("totalDebt")),
            "debt_to_equity": _safe_float(info.get("debtToEquity")),
            "current_ratio": _safe_float(info.get("currentRatio")),
            "quick_ratio": _safe_float(info.get("quickRatio")),
        },
        "income": {
            "revenue": _safe_int(info.get("totalRevenue")),
            "ebitda": _safe_int(info.get("ebitda")),
            "net_income": _safe_int(info.get("netIncomeToCommon")),
            "free_cashflow": _safe_int(info.get("freeCashflow")),
        },
        "company_info": {
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "employees": _safe_int(info.get("fullTimeEmployees")),
            "country": info.get("country"),
            "website": info.get("website"),
            "description": info.get("longBusinessSummary", "")[:500] if info.get("longBusinessSummary") else None,
        },
    }

    # Try to get income statement summary
    try:
        financials = stock.financials
        if financials is not None and not financials.empty:
            latest = financials.iloc[:, 0]
            result["annual_income"] = {
                "year": str(financials.columns[0].year) if hasattr(financials.columns[0], 'year') else str(financials.columns[0]),
                "total_revenue": _safe_int(latest.get("Total Revenue")),
                "gross_profit": _safe_int(latest.get("Gross Profit")),
                "operating_income": _safe_int(latest.get("Operating Income")),
                "net_income": _safe_int(latest.get("Net Income")),
            }
    except Exception:
        pass

    return result
