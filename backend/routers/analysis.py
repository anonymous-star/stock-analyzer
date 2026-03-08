import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from services.technical_service import get_technical_indicators
from services.financial_service import get_financials
from services.news_service import get_news_headlines
from services.ai_service import analyze_stock
from services.recommendation_service import _analyze_single

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_executor = ThreadPoolExecutor(max_workers=3)

VALID_TICKER = re.compile(r'^[A-Za-z0-9.\-]{1,20}$')


@router.post("/{ticker}/analyze")
@limiter.limit("5/minute")
async def analyze(request: Request, ticker: str):
    """Run AI comprehensive analysis on a stock."""
    ticker = ticker.strip().upper()
    if not VALID_TICKER.match(ticker):
        raise HTTPException(status_code=400, detail="유효하지 않은 티커 형식입니다")
    try:
        loop = asyncio.get_running_loop()
        technical_fut = loop.run_in_executor(_executor, get_technical_indicators, ticker)
        financial_fut = loop.run_in_executor(_executor, get_financials, ticker)
        news_fut = loop.run_in_executor(_executor, get_news_headlines, ticker, 5)
        rule_fut = loop.run_in_executor(_executor, _analyze_single, ticker, False)

        technical_data, financial_data, news_headlines, rule_result = await asyncio.gather(
            technical_fut, financial_fut, news_fut, rule_fut
        )

        if "error" in technical_data:
            technical_data = {}

        result = await analyze_stock(
            ticker=ticker,
            technical_data=technical_data,
            financial_data=financial_data,
            news_headlines=news_headlines,
            rule_based=rule_result,
        )

        if "error" in result and result.get("confidence", 0) == 0:
            raise HTTPException(status_code=503, detail="AI 분석 서비스를 사용할 수 없습니다")

        return result

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="분석 중 오류가 발생했습니다")
