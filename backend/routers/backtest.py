from fastapi import APIRouter, Query
from services.backtest_service import run_backtest, clear_backtest_cache
from services.recommendation_service import _cache as rec_cache
from services.cache_service import clear_all_cache as clear_disk_cache, get_cache_stats
from services.ml_service import train_model, get_model_info, reload_model

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

    # 전체 BUY 시그널 요약 통계
    total_buy = sum(r["buy"]["count"] for r in results)
    total_buy_hits = sum(
        int(r["buy"]["count"] * r["buy"]["hit_rate"] / 100)
        for r in results if r["buy"]["count"] > 0
    )
    overall_hit = round(total_buy_hits / total_buy * 100, 1) if total_buy > 0 else 0

    # 수익 기회 + 동적 손절 집계
    opp_1pct_list = []
    opp_3pct_list = []
    sl_hits = []
    sl_returns = []
    base_returns = []
    for r in results:
        opp = r.get("buy_opportunity", {})
        bc = r["buy"]["count"]
        if bc > 0 and opp:
            opp_1pct_list.append(opp.get("opportunity_1pct", 0) * bc / 100)
            opp_3pct_list.append(opp.get("opportunity_3pct", 0) * bc / 100)
            sl_hits.append(opp.get("sl_hit_rate", 0) * bc / 100)
            sl_returns.append(opp.get("sl_avg_return", 0) * bc)
            base_returns.append(r["buy"]["avg_return"] * bc)

    total_opp1 = sum(opp_1pct_list)
    total_opp3 = sum(opp_3pct_list)
    total_sl_hits = sum(sl_hits)
    total_sl_ret = sum(sl_returns)
    total_base_ret = sum(base_returns)

    summary = {
        "total_stocks": len(results),
        "total_signals": total_buy,
        "hit_rate": overall_hit,
        "avg_return": round(total_base_ret / total_buy, 2) if total_buy > 0 else 0,
        "opportunity_1pct": round(total_opp1 / total_buy * 100, 1) if total_buy > 0 else 0,
        "opportunity_3pct": round(total_opp3 / total_buy * 100, 1) if total_buy > 0 else 0,
        "sl_avg_return": round(total_sl_ret / total_buy, 2) if total_buy > 0 else 0,
    }

    return {
        "hold_days": hold_days,
        "count": len(results),
        "summary": summary,
        "results": results,
    }


@router.post("/cache/clear")
async def clear_cache():
    """추천 알고리즘 변경 시 백테스트+추천+디스크 캐시 모두 초기화."""
    clear_backtest_cache()
    rec_cache["data"] = None
    rec_cache["timestamp"] = 0
    clear_disk_cache()
    return {"status": "ok", "message": "백테스트, 추천, 디스크 캐시가 모두 초기화되었습니다"}


@router.get("/cache/stats")
async def cache_stats():
    """디스크 캐시 상태 조회."""
    return get_cache_stats()


@router.post("/model/train")
async def model_train(
    hold_days: int = Query(default=20, ge=5, le=60, description="보유 기간 (일)"),
):
    """LightGBM 모델 학습. 캐시된 10년 데이터 사용."""
    import asyncio
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, train_model, hold_days)
    if "error" not in result:
        # 학습 후 메모리 캐시 초기화 (새 모델 반영)
        clear_backtest_cache()
        rec_cache["data"] = None
        rec_cache["timestamp"] = 0
    return result


@router.get("/model/info")
async def model_info():
    """모델 상태/성능 조회."""
    info = get_model_info()
    if info is None:
        return {"status": "no_model", "message": "학습된 모델이 없습니다. POST /model/train으로 학습하세요."}
    return {"status": "ready", **info}
