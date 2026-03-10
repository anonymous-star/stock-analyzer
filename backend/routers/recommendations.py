from fastapi import APIRouter, Query
from services.recommendation_service import get_recommendations, retry_failed, DEFAULT_TICKERS, _progress, _cache
from services.cache_service import clear_results_cache

router = APIRouter()


@router.get("/recommendations")
async def recommendations(
    limit: int = Query(default=10, ge=1, le=300),
    tickers: str = Query(default=None, description="콤마 구분 티커 목록 (미입력시 기본 풀 사용)"),
    force_refresh: bool = Query(default=False, description="캐시 무시하고 전체 재분석"),
):
    """
    기술적 지표 기반 종목 추천 목록 반환.
    BUY 종목 우선, 점수 높은 순 정렬.
    """
    if force_refresh:
        _cache["data"] = None
        _cache["timestamp"] = 0
        clear_results_cache()
    ticker_list = [t.strip() for t in tickers.split(",")] if tickers else None
    result = await get_recommendations(tickers=ticker_list, limit=limit)
    return {
        "count": len(result),
        "total_pool": len(DEFAULT_TICKERS),
        "failed_count": len(_progress.get("failed_tickers", [])),
        "recommendations": result,
    }


@router.post("/recommendations/retry")
async def recommendations_retry(
    limit: int = Query(default=300, ge=1, le=300),
):
    """실패한 종목만 재분석."""
    result = await retry_failed(limit=limit)
    return {
        "count": len(result),
        "total_pool": len(DEFAULT_TICKERS),
        "failed_count": len(_progress.get("failed_tickers", [])),
        "recommendations": result,
    }


@router.post("/recommendations/clear")
async def recommendations_clear():
    """추천 메모리+디스크 캐시 초기화 → 다음 요청 시 전체 재분석."""
    _cache["data"] = None
    _cache["timestamp"] = 0
    clear_results_cache()
    return {"status": "ok", "message": "추천 캐시 초기화 완료"}


@router.get("/recommendations/progress")
async def recommendations_progress():
    """분석 진행률 조회."""
    has_cache = _cache["data"] is not None and len(_cache["data"]) > 0
    return {
        "total": _progress["total"] or len(DEFAULT_TICKERS),
        "done": _progress["done"],
        "success": _progress.get("success", 0),
        "failed": _progress.get("failed", 0),
        "running": _progress["running"],
        "cached": len(_cache["data"]) if _cache["data"] else 0,
        "has_cache": has_cache,
        "failed_tickers": _progress.get("failed_tickers", []),
    }
