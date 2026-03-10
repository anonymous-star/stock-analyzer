from fastapi import APIRouter, Query
from services.backtest_service import run_backtest, clear_backtest_cache, bt_progress
from services.recommendation_service import _cache as rec_cache
from services.cache_service import clear_results_cache as clear_disk_cache, get_cache_stats
from services.ml_service import train_model, get_model_info, reload_model, ml_progress

router = APIRouter()


@router.get("/backtest")
async def backtest(
    hold_days: int = Query(default=20, ge=5, le=60, description="보유 기간 (일)"),
    limit: int = Query(default=10, ge=1, le=300, description="결과 수"),
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

    # 수익 기회 + 동적 손절 + TP 적중률 집계
    opp_1pct_list = []
    opp_3pct_list = []
    tp_hits_list = []
    sl_returns = []
    base_returns = []
    for r in results:
        opp = r.get("buy_opportunity", {})
        bc = r["buy"]["count"]
        if bc > 0 and opp:
            opp_1pct_list.append(opp.get("opportunity_15pct", 0) * bc / 100)
            opp_3pct_list.append(opp.get("opportunity_3pct", 0) * bc / 100)
            tp_hits_list.append(opp.get("tp_hit_rate", 0) * bc / 100)
            sl_returns.append(opp.get("sl_avg_return", 0) * bc)
            base_returns.append(r["buy"]["avg_return"] * bc)

    total_opp1 = sum(opp_1pct_list)
    total_opp3 = sum(opp_3pct_list)
    total_tp_hits = sum(tp_hits_list)
    total_sl_ret = sum(sl_returns)
    total_base_ret = sum(base_returns)

    summary = {
        "total_stocks": len(results),
        "total_signals": total_buy,
        "hit_rate": overall_hit,
        "tp_hit_rate": round(total_tp_hits / total_buy * 100, 1) if total_buy > 0 else 0,
        "avg_return": round(total_base_ret / total_buy, 2) if total_buy > 0 else 0,
        "opportunity_15pct": round(total_opp1 / total_buy * 100, 1) if total_buy > 0 else 0,
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
    import math, json

    def _sanitize(obj):
        """Replace NaN/Inf with None recursively for JSON safety."""
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    result = await loop.run_in_executor(None, train_model, hold_days)
    result = _sanitize(result)
    if "error" not in result:
        # 학습 후 메모리 캐시 초기화 (새 모델 반영)
        clear_backtest_cache()
        rec_cache["data"] = None
        rec_cache["timestamp"] = 0
    return result


@router.get("/backtest/progress")
async def backtest_progress():
    """백테스트 진행률."""
    return bt_progress


@router.get("/model/progress")
async def model_progress():
    """ML 학습 진행률."""
    return ml_progress


@router.get("/model/info")
async def model_info():
    """모델 상태/성능 조회."""
    info = get_model_info()
    if info is None:
        return {"status": "no_model", "message": "학습된 모델이 없습니다. POST /model/train으로 학습하세요."}
    return {"status": "ready", **info}
