import re
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.stock_service import search_stocks, get_quote, get_price_history
from services.technical_service import get_technical_indicators
from services.financial_service import get_financials
from services.news_service import get_news

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

VALID_TICKER = re.compile(r'^[A-Za-z0-9.\-]{1,20}$')
VALID_PERIODS = {"1mo", "3mo", "6mo", "1y", "2y"}
VALID_INTERVALS = {"1d", "1wk", "1mo"}


def _validate_ticker(ticker: str) -> str:
    ticker = ticker.strip().upper()
    if not VALID_TICKER.match(ticker):
        raise HTTPException(status_code=400, detail="유효하지 않은 티커 형식입니다")
    return ticker


@router.get("/search")
async def search(q: str = Query(..., min_length=1, max_length=50, description="종목명 또는 티커")):
    """Search for stocks by name or ticker symbol."""
    results = search_stocks(q.strip())
    return {"query": q, "results": results}


@router.get("/{ticker}/quote")
async def quote(ticker: str):
    """Get current price and basic info for a ticker."""
    ticker = _validate_ticker(ticker)
    try:
        data = get_quote(ticker)
        if data.get("current_price") is None:
            raise HTTPException(status_code=404, detail=f"티커 '{ticker}'의 데이터를 찾을 수 없습니다")
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="데이터 조회 중 오류가 발생했습니다")


@router.get("/{ticker}/technical")
async def technical(ticker: str):
    """Get technical indicators: MA, RSI, MACD, Bollinger Bands."""
    ticker = _validate_ticker(ticker)
    try:
        data = get_technical_indicators(ticker)
        if "error" in data:
            raise HTTPException(status_code=404, detail=data["error"])
        return data
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="기술적 분석 조회 중 오류가 발생했습니다")


@router.get("/{ticker}/financials")
async def financials(ticker: str):
    """Get financial statements and key metrics."""
    ticker = _validate_ticker(ticker)
    try:
        data = get_financials(ticker)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="재무 데이터 조회 중 오류가 발생했습니다")


@router.get("/{ticker}/news")
async def news(ticker: str, limit: int = Query(default=10, ge=1, le=30)):
    """Get latest news for a ticker."""
    ticker = _validate_ticker(ticker)
    try:
        items = get_news(ticker, limit=limit)
        return {"ticker": ticker, "count": len(items), "news": items}
    except Exception:
        raise HTTPException(status_code=500, detail="뉴스 조회 중 오류가 발생했습니다")


@router.get("/{ticker}/history")
async def history(
    ticker: str,
    period: str = Query(default="6mo", description="1mo/3mo/6mo/1y/2y"),
    interval: str = Query(default="1d", description="1d/1wk/1mo"),
):
    """Get historical price data for charting."""
    ticker = _validate_ticker(ticker)
    if period not in VALID_PERIODS:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 period입니다. 허용값: {', '.join(VALID_PERIODS)}")
    if interval not in VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 interval입니다. 허용값: {', '.join(VALID_INTERVALS)}")
    try:
        data = get_price_history(ticker, period=period, interval=interval)
        if not data:
            raise HTTPException(status_code=404, detail=f"'{ticker}' 히스토리 데이터 없음")
        return {"ticker": ticker, "period": period, "interval": interval, "data": data}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="히스토리 조회 중 오류가 발생했습니다")
