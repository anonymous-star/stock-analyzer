from fastapi import APIRouter, Query
from services.backtest_service import run_backtest, clear_backtest_cache
from services.recommendation_service import _cache as rec_cache

router = APIRouter()


@router.get("/backtest")
async def backtest(
    hold_days: int = Query(default=20, ge=5, le=60, description="보유 기간 (일)"),
    limit: int = Query(default=10, ge=1, le=100, description="결과 수"),
):
    """
    추천 시스템 백테스트 결과.
    과거 1년간 기술적+거래량 지표 기반 시뮬레이션.
    """
    results = await run_backtest(hold_days=hold_days, limit=limit)
    return {
        "hold_days": hold_days,
        "count": len(results),
        "results": results,
    }


@router.post("/cache/clear")
async def clear_cache():
    """추천 알고리즘 변경 시 백테스트+추천 캐시 모두 초기화."""
    clear_backtest_cache()
    rec_cache["data"] = None
    rec_cache["timestamp"] = 0
    return {"status": "ok", "message": "백테스트 및 추천 캐시가 초기화되었습니다"}
