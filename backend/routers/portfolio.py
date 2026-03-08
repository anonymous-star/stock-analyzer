"""가상 포트폴리오 API."""

from fastapi import APIRouter, Query, Header
from pydantic import BaseModel
from services.portfolio_service import (
    buy_stock, sell_stock, sell_by_ticker, get_holdings, get_trade_history,
    get_portfolio_summary, generate_sell_signals, get_all_trades,
)
from services.stock_service import get_quote
from services.advisor_service import generate_advice
from services.auth_service import verify_token

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _get_user_id(authorization: str) -> int:
    """Authorization 헤더에서 user_id 추출. 미인증 시 0."""
    if not authorization:
        return 0
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    payload = verify_token(token)
    return payload["user_id"] if payload else 0


class BuyRequest(BaseModel):
    ticker: str
    name: str = ""
    price: float | None = None
    quantity: int = 1
    tp_pct: float | None = None
    sl_pct: float | None = None
    hold_days: int = 20


class SellRequest(BaseModel):
    position_id: int | None = None
    ticker: str | None = None
    quantity: int | None = None
    price: float | None = None
    reason: str = "manual"


@router.post("/buy")
async def api_buy(req: BuyRequest, authorization: str = Header(default="")):
    """가상 매수."""
    user_id = _get_user_id(authorization)
    price = req.price
    currency = "USD"
    if not price:
        quote = get_quote(req.ticker)
        price = quote.get("current_price")
        currency = quote.get("currency", "USD")
        if not price:
            return {"error": "현재가 조회 실패"}
    name = req.name or req.ticker
    result = buy_stock(
        ticker=req.ticker, name=name, price=price,
        quantity=req.quantity, currency=currency,
        tp_pct=req.tp_pct, sl_pct=req.sl_pct,
        hold_days=req.hold_days, user_id=user_id,
    )
    return result


@router.post("/sell")
async def api_sell(req: SellRequest, authorization: str = Header(default="")):
    """가상 매도 — ticker+quantity 기반 (FIFO) 또는 position_id 기반."""
    user_id = _get_user_id(authorization)
    price = req.price

    # ticker + quantity 기반 매도
    if req.ticker and req.quantity:
        if price is None:
            quote = get_quote(req.ticker)
            price = quote.get("current_price")
            if not price:
                return {"error": "현재가 조회 실패"}
        result = sell_by_ticker(req.ticker, req.quantity, price, req.reason, user_id=user_id)
        return result

    # 레거시: position_id 기반 매도
    if req.position_id:
        if price is None:
            holdings = get_holdings(user_id=user_id)
            pos = next((h for h in holdings if h["id"] == req.position_id), None)
            if pos:
                quote = get_quote(pos["ticker"])
                price = quote.get("current_price")
            if not price:
                return {"error": "현재가 조회 실패"}
        result = sell_stock(req.position_id, price, req.reason, user_id=user_id)
        return result

    return {"error": "ticker+quantity 또는 position_id가 필요합니다"}


@router.get("")
async def api_holdings(authorization: str = Header(default="")):
    """보유 종목 + 현재가 + 매도 시그널 (동일 종목 그룹화)."""
    user_id = _get_user_id(authorization)
    holdings = get_holdings(user_id=user_id)
    if not holdings:
        return {"holdings": [], "grouped": [], "summary": get_portfolio_summary(user_id=user_id)}

    signals = generate_sell_signals(holdings)
    summary = get_portfolio_summary(user_id=user_id)

    # 현재가 기반 미실현 P&L
    total_unrealized = 0
    for s in signals:
        if s.get("return_pct") is not None:
            total_unrealized += s["return_pct"]
    summary["unrealized_avg_return"] = round(total_unrealized / len(signals), 2) if signals else 0

    # 동일 종목 그룹화
    grouped = _group_holdings(signals)

    return {"holdings": signals, "grouped": grouped, "summary": summary}


def _group_holdings(signals: list[dict]) -> list[dict]:
    """동일 종목 포지션을 하나로 합산."""
    from collections import OrderedDict
    groups = OrderedDict()
    for s in signals:
        tk = s["ticker"]
        if tk not in groups:
            groups[tk] = {
                "ticker": tk,
                "name": s.get("name") or tk,
                "currency": s.get("currency", "USD"),
                "positions": [],
                "total_qty": 0,
                "total_cost": 0,
                "current_price": s.get("current_price"),
                "worst_signal": "HOLD",
                "max_urgency": 0,
                "max_sell_score": 0,
                "rsi": s.get("rsi"),
                "volatility": s.get("volatility"),
                "market_regime": s.get("market_regime"),
            }
        g = groups[tk]
        qty = s.get("quantity", 1)
        g["positions"].append(s)
        g["total_qty"] += qty
        g["total_cost"] += s["buy_price"] * qty
        if s.get("current_price"):
            g["current_price"] = s["current_price"]
        # Worst signal wins
        sig_rank = {"SELL": 3, "WATCH": 2, "HOLD": 1}
        if sig_rank.get(s["signal"], 0) > sig_rank.get(g["worst_signal"], 0):
            g["worst_signal"] = s["signal"]
        g["max_urgency"] = max(g["max_urgency"], s.get("urgency", 0))
        g["max_sell_score"] = max(g["max_sell_score"], s.get("sell_score", 0))
        if s.get("rsi"):
            g["rsi"] = s["rsi"]
        if s.get("volatility"):
            g["volatility"] = s["volatility"]
        if s.get("market_regime"):
            g["market_regime"] = s["market_regime"]

    result = []
    for tk, g in groups.items():
        avg_price = round(g["total_cost"] / g["total_qty"], 4) if g["total_qty"] else 0
        cur = g["current_price"]
        ret_pct = round((cur - avg_price) / avg_price * 100, 2) if cur and avg_price else None
        total_value = round(cur * g["total_qty"], 2) if cur else None
        total_pnl = round((cur - avg_price) * g["total_qty"], 2) if cur and avg_price else None

        # Collect all signal reasons from SELL/WATCH positions
        reasons = []
        for p in g["positions"]:
            if p["signal"] in ("SELL", "WATCH") and p.get("signal_reason"):
                reasons.append(p["signal_reason"])

        result.append({
            "ticker": tk,
            "name": g["name"],
            "currency": g["currency"],
            "total_qty": g["total_qty"],
            "avg_price": avg_price,
            "current_price": cur,
            "return_pct": ret_pct,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_cost": round(g["total_cost"], 2),
            "signal": g["worst_signal"],
            "urgency": g["max_urgency"],
            "sell_score": g["max_sell_score"],
            "signal_reasons": reasons,
            "rsi": g["rsi"],
            "volatility": g["volatility"],
            "market_regime": g["market_regime"],
            "positions": [{
                "id": p["id"], "buy_price": p["buy_price"],
                "buy_date": p["buy_date"], "quantity": p.get("quantity", 1),
                "days_held": p.get("days_held", 0), "hold_days": p.get("hold_days", 20),
                "tp_price": p.get("tp_price"), "sl_price": p.get("sl_price"),
                "return_pct": p.get("return_pct"), "signal": p["signal"],
            } for p in g["positions"]],
        })

    # Sort: SELL first, then by urgency/sell_score
    sig_order = {"SELL": 0, "WATCH": 1, "HOLD": 2}
    result.sort(key=lambda x: (sig_order.get(x["signal"], 9), -x["urgency"], -x["sell_score"]))
    return result


@router.get("/history")
async def api_history(limit: int = Query(default=100, ge=1, le=500), authorization: str = Header(default="")):
    """전체 거래 이력 (매수+매도)."""
    user_id = _get_user_id(authorization)
    all_trades = get_all_trades(limit, user_id=user_id)
    sell_trades = [t for t in all_trades if t["status"] == "closed"]
    buy_trades = [t for t in all_trades]  # all are buys

    # Cumulative P&L
    cum_pnl = 0
    cum_trades = []
    for t in reversed(sell_trades):
        if t.get("return_pct") is not None:
            cum_pnl += (t["sell_price"] - t["buy_price"]) * t.get("quantity", 1)
        cum_trades.append({"date": t.get("sell_date"), "cum_pnl": round(cum_pnl, 2)})
    cum_trades.reverse()

    return {
        "trades": all_trades,
        "sell_count": len(sell_trades),
        "buy_count": len(buy_trades),
        "count": len(all_trades),
        "cumulative_pnl": cum_trades,
    }


@router.get("/market-regime")
async def api_market_regime():
    """시장 레짐만 빠르게 반환 (Dashboard 경고용)."""
    from services.ml_service import get_current_market_features
    mkt_us = get_current_market_features(is_korean=False)
    breadth = mkt_us.get("market_breadth", 1.5)
    regime = "하락장" if breadth == 0 else "약세장" if breadth <= 1 else "보통" if breadth <= 2 else "상승장"
    return {
        "market_regime": regime,
        "market_breadth": breadth,
        "trend_20d": mkt_us.get("market_trend_20d", 0),
        "volatility": mkt_us.get("market_volatility", 3),
    }


@router.get("/advisor")
async def api_advisor(authorization: str = Header(default="")):
    """AI 투자 어드바이저 — LLM 기반 맞춤 가이드."""
    from services.ml_service import get_current_market_features
    from services.recommendation_service import get_recommendations

    user_id = _get_user_id(authorization)

    # 1. 포트폴리오 상태
    holdings_raw = get_holdings(user_id=user_id)
    signals = generate_sell_signals(holdings_raw) if holdings_raw else []
    summary = get_portfolio_summary(user_id=user_id)

    # 2. 시장 레짐
    mkt_us = get_current_market_features(is_korean=False)
    breadth = mkt_us.get("market_breadth", 1.5)
    regime = "하락장" if breadth == 0 else "약세장" if breadth <= 1 else "보통" if breadth <= 2 else "상승장"

    # 3. BUY 후보 (confidence 순) — 보유 종목 제외
    held_tickers = {s["ticker"] for s in signals}
    recs = await get_recommendations(limit=100)
    buy_candidates = []
    for r in recs:
        if r.get("recommendation") == "BUY" and r["ticker"] not in held_tickers:
            buy_candidates.append({
                "ticker": r["ticker"],
                "name": r.get("name"),
                "score": r.get("score"),
                "confidence": r.get("confidence"),
                "rsi": r.get("rsi"),
                "bt_hit_rate": "N/A",
            })
    buy_candidates.sort(key=lambda x: -(x.get("confidence") or 0))

    # 4. 백테스트 KPI (간단 집계)
    backtest_kpi = {}
    try:
        from services.backtest_service import run_backtest
        bt = await run_backtest(hold_days=20, limit=100)
        total_buy = sum(r["buy"]["count"] for r in bt)
        total_hits = sum(int(r["buy"]["count"] * r["buy"]["hit_rate"] / 100) for r in bt if r["buy"]["count"] > 0)
        total_ret = sum(r["buy"]["avg_return"] * r["buy"]["count"] for r in bt)
        opp_total = 0
        opp_count = 0
        for r in bt:
            opp = r.get("buy_opportunity", {})
            bc = r["buy"]["count"]
            if bc > 0 and opp.get("opportunity_1pct") is not None:
                opp_total += opp["opportunity_1pct"] * bc / 100
                opp_count += bc

        # BUY 후보에 10년 적중률 매핑
        bt_map = {r["ticker"]: r for r in bt}
        for c in buy_candidates:
            bt_r = bt_map.get(c["ticker"])
            if bt_r and bt_r["buy"]["count"] >= 10:
                c["bt_hit_rate"] = f"{bt_r['buy']['hit_rate']}%"

        backtest_kpi = {
            "hit_rate": round(total_hits / total_buy * 100, 1) if total_buy else 0,
            "avg_return": round(total_ret / total_buy, 1) if total_buy else 0,
            "opp_rate": round(opp_total / opp_count * 100, 1) if opp_count else 0,
        }
    except Exception:
        pass

    # 5. LLM 호출
    context = {
        "market": {
            "regime": regime,
            "trend_20d": mkt_us.get("market_trend_20d", 0),
            "volatility": mkt_us.get("market_volatility", 3),
            "breadth": breadth,
        },
        "holdings": signals,
        "sell_signals": [s for s in signals if s.get("signal") in ("SELL", "WATCH")],
        "buy_candidates": buy_candidates[:8],
        "summary": summary,
        "backtest_kpi": backtest_kpi,
    }

    advice = await generate_advice(context)
    advice["market_regime"] = regime
    advice["market_breadth"] = breadth
    advice["buy_candidates_count"] = len(buy_candidates)
    advice["high_confidence_count"] = len([c for c in buy_candidates if (c.get("confidence") or 0) >= 80])
    return advice
