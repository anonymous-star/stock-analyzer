"""가상 포트폴리오 관리 서비스 (SQLite)."""

import os
import sqlite3
import time
from datetime import datetime, timedelta

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_PATH = os.path.join(_DATA_DIR, "portfolio.db")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(_DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            name TEXT,
            buy_price REAL NOT NULL,
            buy_date TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'open',
            sell_price REAL,
            sell_date TEXT,
            sell_reason TEXT,
            tp_price REAL,
            sl_price REAL,
            hold_days INTEGER DEFAULT 20,
            created_at REAL DEFAULT (strftime('%s','now')),
            user_id INTEGER DEFAULT 0
        )
    """)
    # user_id 컬럼 마이그레이션 (기존 DB 호환)
    try:
        conn.execute("ALTER TABLE positions ADD COLUMN user_id INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 이미 존재
    conn.commit()
    return conn


def buy_stock(ticker: str, name: str, price: float, quantity: int,
              currency: str = "USD", tp_pct: float = None, sl_pct: float = None,
              hold_days: int = 20, user_id: int = 0) -> dict:
    """가상 매수 실행."""
    conn = _get_conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    tp_price = round(price * (1 + tp_pct / 100), 4) if tp_pct else None
    sl_price = round(price * (1 + sl_pct / 100), 4) if sl_pct else None
    cur = conn.execute(
        """INSERT INTO positions (ticker, name, buy_price, buy_date, quantity,
           currency, tp_price, sl_price, hold_days, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ticker, name, price, now, quantity, currency, tp_price, sl_price, hold_days, user_id)
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return {"id": pid, "ticker": ticker, "buy_price": price, "quantity": quantity,
            "buy_date": now, "tp_price": tp_price, "sl_price": sl_price}


def sell_stock(position_id: int, price: float, reason: str = "manual", user_id: int = 0) -> dict:
    """가상 매도 실행 (단일 포지션)."""
    conn = _get_conn()
    row = conn.execute("SELECT * FROM positions WHERE id=? AND status='open' AND user_id=?",
                       (position_id, user_id)).fetchone()
    if not row:
        conn.close()
        return {"error": "포지션을 찾을 수 없습니다"}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute(
        "UPDATE positions SET status='closed', sell_price=?, sell_date=?, sell_reason=? WHERE id=?",
        (price, now, reason, position_id)
    )
    conn.commit()
    ret = (price - row["buy_price"]) / row["buy_price"] * 100
    conn.close()
    return {"id": position_id, "ticker": row["ticker"], "sell_price": price,
            "return_pct": round(ret, 2), "reason": reason}


def sell_by_ticker(ticker: str, quantity: int, price: float, reason: str = "manual", user_id: int = 0) -> dict:
    """수량 기반 매도 — FIFO(선입선출) 방식으로 오래된 포지션부터 매도."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions WHERE ticker=? AND status='open' AND user_id=? ORDER BY buy_date ASC",
        (ticker, user_id)
    ).fetchall()
    if not rows:
        conn.close()
        return {"error": "보유 포지션이 없습니다"}

    total_available = sum(r["quantity"] for r in rows)
    if quantity > total_available:
        conn.close()
        return {"error": f"보유 수량 부족 (보유: {total_available}, 요청: {quantity})"}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    remaining = quantity
    sold_positions = []
    total_cost = 0
    total_qty_sold = 0

    for row in rows:
        if remaining <= 0:
            break
        pos_qty = row["quantity"]
        if pos_qty <= remaining:
            # 포지션 전체 매도
            conn.execute(
                "UPDATE positions SET status='closed', sell_price=?, sell_date=?, sell_reason=? WHERE id=?",
                (price, now, reason, row["id"])
            )
            total_cost += row["buy_price"] * pos_qty
            total_qty_sold += pos_qty
            remaining -= pos_qty
            sold_positions.append({"id": row["id"], "qty": pos_qty, "buy_price": row["buy_price"]})
        else:
            # 포지션 일부만 매도 → 기존 포지션 수량 줄이고, 매도분 새 레코드 생성
            new_qty = pos_qty - remaining
            conn.execute("UPDATE positions SET quantity=? WHERE id=?", (new_qty, row["id"]))
            conn.execute(
                """INSERT INTO positions (ticker, name, buy_price, buy_date, quantity,
                   currency, status, sell_price, sell_date, sell_reason,
                   tp_price, sl_price, hold_days, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'closed', ?, ?, ?, ?, ?, ?, ?)""",
                (row["ticker"], row["name"], row["buy_price"], row["buy_date"], remaining,
                 row["currency"], price, now, reason,
                 row["tp_price"], row["sl_price"], row["hold_days"], row["created_at"])
            )
            total_cost += row["buy_price"] * remaining
            total_qty_sold += remaining
            sold_positions.append({"id": row["id"], "qty": remaining, "buy_price": row["buy_price"]})
            remaining = 0

    conn.commit()
    conn.close()

    avg_buy = total_cost / total_qty_sold if total_qty_sold else 0
    ret_pct = round((price - avg_buy) / avg_buy * 100, 2) if avg_buy else 0
    total_pnl = round((price - avg_buy) * total_qty_sold, 2)

    return {
        "ticker": ticker,
        "quantity_sold": total_qty_sold,
        "avg_buy_price": round(avg_buy, 4),
        "sell_price": price,
        "return_pct": ret_pct,
        "total_pnl": total_pnl,
        "reason": reason,
        "positions_affected": len(sold_positions),
    }


def get_holdings(user_id: int = 0) -> list[dict]:
    """보유 중인 포지션 목록."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions WHERE status='open' AND user_id=? ORDER BY buy_date DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trade_history(limit: int = 50, user_id: int = 0) -> list[dict]:
    """거래 내역 (매도 완료)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions WHERE status='closed' AND user_id=? ORDER BY sell_date DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["return_pct"] = round((d["sell_price"] - d["buy_price"]) / d["buy_price"] * 100, 2) if d.get("sell_price") else 0
        result.append(d)
    return result


def get_all_trades(limit: int = 100, user_id: int = 0) -> list[dict]:
    """모든 거래 이력 (매수+매도 포함)."""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM positions WHERE user_id=? ORDER BY COALESCE(sell_date, buy_date) DESC LIMIT ?",
        (user_id, limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if d["status"] == "closed" and d.get("sell_price"):
            d["return_pct"] = round((d["sell_price"] - d["buy_price"]) / d["buy_price"] * 100, 2)
        else:
            d["return_pct"] = None
        result.append(d)
    return result


def get_portfolio_summary(user_id: int = 0) -> dict:
    """포트폴리오 전체 요약."""
    conn = _get_conn()
    open_rows = conn.execute("SELECT * FROM positions WHERE status='open' AND user_id=?", (user_id,)).fetchall()
    closed_rows = conn.execute("SELECT * FROM positions WHERE status='closed' AND user_id=?", (user_id,)).fetchall()
    conn.close()

    total_invested = sum(r["buy_price"] * r["quantity"] for r in open_rows)
    closed_pnl_amounts = []
    closed_returns = []
    for r in closed_rows:
        if r["sell_price"]:
            ret = (r["sell_price"] - r["buy_price"]) / r["buy_price"] * 100
            pnl = (r["sell_price"] - r["buy_price"]) * r["quantity"]
            closed_returns.append(ret)
            closed_pnl_amounts.append(pnl)

    wins = sum(1 for r in closed_returns if r > 0)
    total_pnl = sum(closed_pnl_amounts)
    total_buy_count = len(open_rows) + len(closed_rows)
    return {
        "open_count": len(open_rows),
        "closed_count": len(closed_rows),
        "total_trades": total_buy_count,
        "total_invested": round(total_invested, 2),
        "closed_avg_return": round(sum(closed_returns) / len(closed_returns), 2) if closed_returns else 0,
        "closed_win_rate": round(wins / len(closed_returns) * 100, 1) if closed_returns else 0,
        "closed_total_pnl": round(total_pnl, 2),
        "closed_total_return_sum": round(sum(closed_returns), 2),
    }


def _get_market_regime() -> dict:
    """현재 시장 레짐 조회 (캐시)."""
    try:
        from services.ml_service import get_current_market_features
        return get_current_market_features(is_korean=False)
    except Exception:
        return {"market_breadth": 1.5, "market_trend_20d": 0, "market_volatility": 3}


def generate_sell_signals(holdings: list[dict]) -> list[dict]:
    """
    보유 종목별 매도 타이밍 시그널 생성.
    v2: 트레일링 스탑 + 시장 레짐 + 강화된 기술적 신호 + 스코어 기반 매도.
    """
    from services.technical_service import get_technical_indicators
    from services.stock_service import get_quote

    signals = []
    today = datetime.now()
    market = _get_market_regime()
    mkt_breadth = market.get("market_breadth", 1.5)
    mkt_trend = market.get("market_trend_20d", 0)

    # 시장 레짐에 따른 손절 배율 (하락장에서 타이트하게)
    if mkt_breadth == 0 or mkt_trend < -5:
        sl_multiplier = 0.6   # 하락장: 손절선 40% 타이트
        tp_multiplier = 0.7   # 익절도 빨리
    elif mkt_breadth <= 1:
        sl_multiplier = 0.8
        tp_multiplier = 0.85
    else:
        sl_multiplier = 1.0
        tp_multiplier = 1.0

    for pos in holdings:
        ticker = pos["ticker"]
        try:
            tech = get_technical_indicators(ticker)
            quote = get_quote(ticker)
            current_price = quote.get("current_price")
            if not current_price:
                signals.append({**pos, "signal": "HOLD", "signal_reason": "가격 조회 실패",
                                "current_price": None, "return_pct": None, "urgency": 0,
                                "sell_score": 0})
                continue

            buy_price = pos["buy_price"]
            ret_pct = round((current_price - buy_price) / buy_price * 100, 2)

            # 보유일수 계산
            try:
                buy_dt = datetime.strptime(pos["buy_date"], "%Y-%m-%d %H:%M")
            except ValueError:
                buy_dt = datetime.strptime(pos["buy_date"], "%Y-%m-%d")
            days_held = (today - buy_dt).days

            signal = "HOLD"
            reason = ""
            urgency = 0  # 0=낮음, 1=보통, 2=높음, 3=즉시
            sell_score = 0  # 매도 점수 (높을수록 매도 권장)

            # === 1. 손절 체크 (시장 레짐 반영) ===
            sl_price = pos.get("sl_price")
            if sl_price:
                # 시장 하락장이면 손절선을 더 타이트하게 조정
                effective_sl = buy_price + (sl_price - buy_price) * sl_multiplier
                if current_price <= effective_sl:
                    signal = "SELL"
                    if sl_multiplier < 1.0:
                        reason = f"시장 하락장 조기 손절 (SL {effective_sl:,.0f}, 원래 {sl_price:,.0f})"
                    else:
                        reason = f"손절선 도달 (SL {sl_price:,.0f})"
                    urgency = 3
                    sell_score = 10

            # === 2. 트레일링 스탑 (수익 보호) ===
            if signal != "SELL" and ret_pct > 3:
                # 수익이 3%+ 나면 트레일링 스탑 작동
                # 최고점 대비 하락폭 체크 (5일 모멘텀 활용)
                mom5 = tech.get("momentum_5d")
                volatility = tech.get("volatility") or 3
                # 트레일링 임계값: 변동성 기반
                trail_threshold = max(2.0, volatility * 0.8)

                if mom5 is not None and mom5 < -trail_threshold and ret_pct > 0:
                    signal = "SELL"
                    reason = f"트레일링 스탑: 수익 +{ret_pct:.1f}% 중 5일 {mom5:+.1f}% 급락"
                    urgency = 3
                    sell_score = 8

            # === 3. 익절 체크 (시장 레짐 반영) ===
            tp_price = pos.get("tp_price")
            if signal != "SELL" and tp_price:
                effective_tp = buy_price + (tp_price - buy_price) * tp_multiplier
                if current_price >= effective_tp:
                    signal = "SELL"
                    if tp_multiplier < 1.0:
                        reason = f"시장 약세 조기 익절 (TP {effective_tp:,.0f}, 원래 {tp_price:,.0f})"
                    else:
                        reason = f"목표가 도달 (TP {tp_price:,.0f})"
                    urgency = 2
                    sell_score = 7

            # === 4. 보유기간 초과 ===
            max_hold = pos.get("hold_days") or 20
            if signal != "SELL" and days_held >= max_hold:
                signal = "SELL"
                reason = f"보유기간 {max_hold}일 초과 ({days_held}일)"
                urgency = 2
                sell_score = 6

            # === 5. 강화된 기술적 매도 신호 (점수 기반) ===
            # 매수 후 최소 2일은 기술적 매도 시그널 억제 (당일 매수 즉시 SELL 방지)
            if signal != "SELL" and days_held >= 2:
                rsi = tech.get("rsi")
                macd_signal = (tech.get("signals") or {}).get("macd_signal")
                ma_trend = (tech.get("signals") or {}).get("ma_trend")
                bb_pos = (tech.get("signals") or {}).get("bb_position")
                macd_accel = tech.get("macd_accel")
                ma20_slope = tech.get("ma20_slope")
                volatility = tech.get("volatility")
                trend_20d = tech.get("trend_20d")

                tech_reasons = []

                # RSI 과매수 (점수 +2~3)
                if rsi and rsi > 80:
                    tech_reasons.append(f"RSI {rsi:.0f} 극단적 과매수")
                    sell_score += 3
                    urgency = max(urgency, 3)
                elif rsi and rsi > 70:
                    tech_reasons.append(f"RSI {rsi:.0f} 과매수")
                    sell_score += 2
                    urgency = max(urgency, 2)

                # MACD 데드크로스 (+1~2)
                if macd_signal == "bearish":
                    tech_reasons.append("MACD 데드크로스")
                    sell_score += 1
                    urgency = max(urgency, 1)
                    if macd_accel is not None and macd_accel < -0.3:
                        tech_reasons.append("MACD 급격 하락")
                        sell_score += 1

                # MA 역배열 (+2)
                if ma_trend == "bearish":
                    tech_reasons.append("이동평균 역배열")
                    sell_score += 2
                    urgency = max(urgency, 1)

                # 볼린저밴드 상단 돌파 (+1)
                if bb_pos == "above_upper":
                    tech_reasons.append("볼린저밴드 상단 돌파")
                    sell_score += 1
                    urgency = max(urgency, 1)

                # MA20 기울기 급락 (+1)
                if ma20_slope is not None and ma20_slope < -1.0:
                    tech_reasons.append(f"MA20 기울기 {ma20_slope:.2f}% 급락")
                    sell_score += 1

                # 20일 추세 급락 (+1~2)
                if trend_20d is not None and trend_20d < -10:
                    tech_reasons.append(f"20일 {trend_20d:+.1f}% 급락 추세")
                    sell_score += 2
                    urgency = max(urgency, 2)
                elif trend_20d is not None and trend_20d < -5:
                    sell_score += 1

                # 고변동성 + 수익 → 익절 권장 (+1)
                if volatility is not None and volatility > 4 and ret_pct > 2:
                    tech_reasons.append(f"고변동성 {volatility:.1f}% + 수익 중 — 익절 권장")
                    sell_score += 1
                    urgency = max(urgency, 1)

                # 시장 하락장 보너스 매도 점수
                if mkt_breadth == 0:
                    sell_score += 2
                    if not any("시장" in r for r in tech_reasons):
                        tech_reasons.append("시장 전체 하락장")
                elif mkt_breadth <= 1 and mkt_trend < -3:
                    sell_score += 1

                # 점수 기반 판정
                if sell_score >= 5:
                    signal = "SELL"
                    reason = " + ".join(tech_reasons[:3])
                elif sell_score >= 3:
                    signal = "WATCH"
                    reason = " + ".join(tech_reasons[:3])
                elif tech_reasons:
                    signal = "WATCH" if len(tech_reasons) >= 2 else "HOLD"
                    reason = " + ".join(tech_reasons[:2])

            # === 6. 수익 상태별 조언 ===
            if signal == "HOLD":
                if ret_pct > 8:
                    reason = f"수익 +{ret_pct:.1f}% — 일부 익절 강력 권장"
                    urgency = max(urgency, 2)
                    sell_score = max(sell_score, 3)
                elif ret_pct > 5:
                    reason = f"수익 +{ret_pct:.1f}% — 일부 익절 고려"
                    urgency = max(urgency, 1)
                elif ret_pct < -3:
                    reason = f"손실 {ret_pct:.1f}% — SL 근접 주의"
                    urgency = max(urgency, 1)
                elif days_held > max_hold * 0.7:
                    reason = f"보유 {days_held}일 — 만기({max_hold}일) 근접"
                    urgency = max(urgency, 1)
                else:
                    reason = "정상 보유 중"

            signals.append({
                "id": pos["id"],
                "ticker": ticker,
                "name": pos.get("name") or ticker,
                "buy_price": buy_price,
                "buy_date": pos["buy_date"],
                "current_price": current_price,
                "return_pct": ret_pct,
                "days_held": days_held,
                "hold_days": pos.get("hold_days") or 20,
                "tp_price": pos.get("tp_price"),
                "sl_price": pos.get("sl_price"),
                "signal": signal,
                "signal_reason": reason,
                "urgency": urgency,
                "sell_score": sell_score,
                "rsi": tech.get("rsi"),
                "ma_trend": (tech.get("signals") or {}).get("ma_trend"),
                "macd_accel": tech.get("macd_accel"),
                "volatility": tech.get("volatility"),
                "trend_20d": tech.get("trend_20d"),
                "market_regime": "하락장" if mkt_breadth == 0 else "약세장" if mkt_breadth <= 1 else "보통" if mkt_breadth <= 2 else "상승장",
                "currency": pos.get("currency", "USD"),
                "quantity": pos.get("quantity", 1),
            })
        except Exception as e:
            signals.append({
                "id": pos["id"], "ticker": ticker, "name": pos.get("name"),
                "buy_price": pos["buy_price"], "buy_date": pos["buy_date"],
                "current_price": None, "return_pct": None,
                "signal": "HOLD", "signal_reason": f"분석 실패: {str(e)[:30]}",
                "urgency": 0, "sell_score": 0, "days_held": 0, "hold_days": 20,
                "currency": pos.get("currency", "USD"), "quantity": pos.get("quantity", 1),
            })

    # urgency 높은 순, 같으면 sell_score 높은 순
    signals.sort(key=lambda x: (-x.get("urgency", 0), -x.get("sell_score", 0)))
    return signals
