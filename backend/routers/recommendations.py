from fastapi import APIRouter, Query
from services.recommendation_service import get_recommendations, DEFAULT_TICKERS

router = APIRouter()


@router.get("/recommendations")
async def recommendations(
    limit: int = Query(default=10, ge=1, le=30),
    tickers: str = Query(default=None, description="콤마 구분 티커 목록 (미입력시 기본 풀 사용)"),
):
    """
    기술적 지표 기반 종목 추천 목록 반환.
    BUY 종목 우선, 점수 높은 순 정렬.
    """
    ticker_list = [t.strip() for t in tickers.split(",")] if tickers else None
    result = get_recommendations(tickers=ticker_list, limit=limit)
    return {
        "count": len(result),
        "recommendations": result,
    }
