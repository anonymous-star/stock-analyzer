"""AI 투자 어드바이저 — LLM 기반 맞춤형 가이드 생성."""

import os
import json
import re
import time
from groq import Groq


_cache = {"data": None, "timestamp": 0}
CACHE_TTL = 1800  # 30분


def _build_advisor_prompt(context: dict) -> str:
    """포트폴리오 + 시장 + 시그널 데이터로 프롬프트 생성."""
    market = context.get("market", {})
    holdings = context.get("holdings", [])
    sell_signals = context.get("sell_signals", [])
    buy_candidates = context.get("buy_candidates", [])
    summary = context.get("summary", {})
    backtest_kpi = context.get("backtest_kpi", {})

    # 매도 시그널 요약
    sell_items = []
    for s in sell_signals:
        if s.get("signal") in ("SELL", "WATCH"):
            sell_items.append(
                f"  - {s['ticker']}({s.get('name','')[:10]}): "
                f"수익률 {s.get('return_pct', 0):+.1f}%, "
                f"신호={s['signal']}, "
                f"사유={s.get('signal_reason','')}, "
                f"RSI={s.get('rsi','?')}, "
                f"변동성={s.get('volatility','?')}%, "
                f"보유 {s.get('days_held',0)}/{s.get('hold_days',20)}일"
            )

    # BUY 후보 요약 (confidence 80%+)
    buy_items = []
    for b in buy_candidates[:8]:
        buy_items.append(
            f"  - {b['ticker']}({b.get('name','')[:10]}): "
            f"점수 +{b.get('score',0)}, "
            f"확신도 {b.get('confidence',0)}%, "
            f"RSI {b.get('rsi','?')}, "
            f"10년적중 {b.get('bt_hit_rate', 'N/A')}"
        )

    holdings_text = f"{len(holdings)}개 보유" if holdings else "보유 종목 없음"
    sell_text = "\n".join(sell_items) if sell_items else "  없음"
    buy_text = "\n".join(buy_items) if buy_items else "  없음"

    return f"""당신은 개인 투자자를 위한 AI 투자 코치입니다.
아래 데이터를 분석해서 **지금 즉시 실행할 수 있는 구체적인 행동 가이드**를 한국어로 작성해주세요.

## 현재 시장 상황
- 시장 레짐: {market.get('regime', '보통')}
- 시장 추세 (20일): {market.get('trend_20d', 0):+.1f}%
- 시장 변동성: {market.get('volatility', 3):.1f}%
- 시장 breadth (MA 위치): {market.get('breadth', 1.5)}

## 포트폴리오 현황
- {holdings_text}
- 실현 수익률: {summary.get('closed_avg_return', 0):+.1f}%
- 승률: {summary.get('closed_win_rate', 0):.0f}%

## 매도 시그널 (SELL/WATCH)
{sell_text}

## BUY 후보 (확신도 높은 순)
{buy_text}

## 10년 백테스트 KPI
- BUY 적중률: {backtest_kpi.get('hit_rate', 0)}%
- 평균 수익률: {backtest_kpi.get('avg_return', 0):+.1f}%
- 1%+ 수익 기회: {backtest_kpi.get('opp_rate', 0)}%

---

아래 JSON 형식으로만 응답하세요. 코드블록 없이 순수 JSON:

{{
  "market_summary": "현재 시장 상태 한 줄 요약 (이모지 포함)",
  "urgency": "low" 또는 "medium" 또는 "high",
  "actions": [
    {{
      "type": "sell" 또는 "buy" 또는 "hold" 또는 "warn",
      "ticker": "종목코드 또는 null",
      "title": "행동 제목 (짧게)",
      "detail": "구체적 실행 방법 2~3문장",
      "priority": 1~5
    }}
  ],
  "weekly_strategy": "이번 주 투자 전략 3~4문장",
  "risk_alert": "현재 가장 주의할 리스크 1~2문장 (없으면 null)",
  "tip": "초보 투자자를 위한 실용적 팁 한 줄"
}}

규칙:
1. actions는 우선순위 높은 것부터 최대 6개
2. 매도가 급한 종목은 반드시 포함하고 priority 5 부여
3. BUY 추천은 확신도 80%+ 또는 10년 검증된 것만
4. 하락장이면 "현금 비중 유지" 조언 반드시 포함
5. 쉬운 한국어로, 전문용어는 괄호 안에 설명 추가
6. 수익률/손절 퍼센트 등 구체적 숫자 포함
7. 이미 보유 중인 종목은 절대 BUY 추천하지 마세요 (BUY 후보 목록에는 보유 종목이 이미 제외되어 있습니다)
8. 동일 종목에 대해 매수와 매도를 동시에 추천하지 마세요"""


def _parse_advisor_response(text: str) -> dict:
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    text = text.strip()
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    return {
        "market_summary": "분석 결과를 불러올 수 없습니다.",
        "urgency": "low",
        "actions": [],
        "weekly_strategy": text[:300] if text else "",
        "risk_alert": None,
        "tip": "",
    }


async def generate_advice(context: dict) -> dict:
    """LLM 호출하여 투자 어드바이스 생성."""
    import asyncio

    # 캐시 확인
    now = time.time()
    if _cache["data"] and (now - _cache["timestamp"]) < CACHE_TTL:
        return _cache["data"]

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "error": "GROQ_API_KEY not configured",
            "market_summary": "API 키가 설정되지 않았습니다.",
            "actions": [],
        }

    client = Groq(api_key=api_key)
    prompt = _build_advisor_prompt(context)

    def _call_llm():
        return client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

    response = await asyncio.to_thread(_call_llm)

    result = _parse_advisor_response(response.choices[0].message.content)
    result["generated_at"] = time.strftime("%Y-%m-%d %H:%M")
    _cache["data"] = result
    _cache["timestamp"] = now
    return result
