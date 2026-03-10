from fastapi import APIRouter, Query
from services.recommendation_service import get_recommendations, DEFAULT_TICKERS, _progress, _cache

router = APIRouter()


@router.get("/recommendations")
async def recommendations(
    limit: int = Query(default=10, ge=1, le=300),
    tickers: str = Query(default=None, description="콤마 구분 티커 목록 (미입력시 기본 풀 사용)"),
):
    """
    기술적 지표 기반 종목 추천 목록 반환.
    BUY 종목 우선, 점수 높은 순 정렬.
    """
    ticker_list = [t.strip() for t in tickers.split(",")] if tickers else None
    result = await get_recommendations(tickers=ticker_list, limit=limit)
    return {
        "count": len(result),
        "total_pool": len(DEFAULT_TICKERS),
        "recommendations": result,
    }


@router.get("/recommendations/progress")
async def recommendations_progress():
    """분석 진행률 조회."""
    has_cache = _cache["data"] is not None and len(_cache["data"]) > 0
    return {
        "total": _progress["total"] or len(DEFAULT_TICKERS),
        "done": _progress["done"],
        "running": _progress["running"],
        "cached": len(_cache["data"]) if _cache["data"] else 0,
        "has_cache": has_cache,
    }
