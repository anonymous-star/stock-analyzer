import os
import json
import re
from google import genai


def _build_prompt(ticker: str, technical_data: dict, financial_data: dict, news_headlines: list[str]) -> str:
    tech_lines = [f"티커: {ticker}"]
    if technical_data:
        price = technical_data.get("current_price")
        if price:
            tech_lines.append(f"현재가: {price:,.2f}")
        for ma in ["ma20", "ma50", "ma200"]:
            val = technical_data.get(ma)
            if val:
                tech_lines.append(f"{ma.upper()}: {val:,.2f}")
        rsi = technical_data.get("rsi")
        if rsi:
            tech_lines.append(f"RSI(14): {rsi:.1f}")
        macd = technical_data.get("macd")
        if macd:
            tech_lines.append(f"MACD: {macd.get('macd', 0):.4f}, Signal: {macd.get('signal', 0):.4f}, Hist: {macd.get('histogram', 0):.4f}")
        bb = technical_data.get("bollinger_bands")
        if bb:
            tech_lines.append(f"볼린저밴드 상단: {bb.get('upper', 0):,.2f}, 중단: {bb.get('mid', 0):,.2f}, 하단: {bb.get('lower', 0):,.2f}")
        signals = technical_data.get("signals", {})
        if signals:
            tech_lines.append(f"기술적 신호: {json.dumps(signals, ensure_ascii=False)}")

    fin_lines = []
    if financial_data:
        val = financial_data.get("valuation", {})
        if val.get("pe_ratio"):
            fin_lines.append(f"PER: {val['pe_ratio']:.1f}배")
        if val.get("pb_ratio"):
            fin_lines.append(f"PBR: {val['pb_ratio']:.2f}배")
        if val.get("peg_ratio"):
            fin_lines.append(f"PEG: {val['peg_ratio']:.2f}")
        prof = financial_data.get("profitability", {})
        if prof.get("profit_margin"):
            fin_lines.append(f"순이익률: {prof['profit_margin']*100:.1f}%")
        if prof.get("roe"):
            fin_lines.append(f"ROE: {prof['roe']*100:.1f}%")
        growth = financial_data.get("growth", {})
        if growth.get("revenue_growth"):
            fin_lines.append(f"매출 성장률: {growth['revenue_growth']*100:.1f}%")
        if growth.get("earnings_growth"):
            fin_lines.append(f"이익 성장률: {growth['earnings_growth']*100:.1f}%")
        company = financial_data.get("company_info", {})
        if company.get("sector"):
            fin_lines.append(f"섹터: {company['sector']}")

    news_text = "\n".join(f"- {h}" for h in news_headlines[:5]) if news_headlines else "뉴스 없음"

    return f"""당신은 전문 주식 애널리스트입니다. 아래 데이터를 바탕으로 {ticker} 종목을 분석해주세요.

## 기술적 분석 데이터
{chr(10).join(tech_lines)}

## 재무 데이터
{chr(10).join(fin_lines) if fin_lines else "재무 데이터 없음"}

## 최근 뉴스 헤드라인
{news_text}

위 데이터를 종합하여 다음 형식의 JSON으로만 응답해주세요. 코드블록(```)이나 다른 텍스트 없이 순수 JSON만 반환하세요:

{{
  "recommendation": "BUY" 또는 "HOLD" 또는 "SELL",
  "confidence": 1~5 사이 정수 (1=낮음, 5=높음),
  "target_price_low": 예상 하단 목표가 숫자 또는 null,
  "target_price_high": 예상 상단 목표가 숫자 또는 null,
  "investment_points": ["핵심 투자 포인트 1", "핵심 투자 포인트 2", "핵심 투자 포인트 3"],
  "risk_factors": ["리스크 요인 1", "리스크 요인 2"],
  "technical_summary": "기술적 분석 요약 2-3문장",
  "fundamental_summary": "펀더멘털 분석 요약 2-3문장",
  "overall_summary": "종합 투자 의견 3-4문장"
}}"""


def parse_analysis_response(text: str) -> dict:
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
        "recommendation": "HOLD",
        "confidence": 1,
        "target_price_low": None,
        "target_price_high": None,
        "investment_points": [],
        "risk_factors": [],
        "technical_summary": "",
        "fundamental_summary": "",
        "overall_summary": text[:500] if text else "분석 결과를 파싱하는데 실패했습니다.",
    }


async def analyze_stock(
    ticker: str,
    technical_data: dict,
    financial_data: dict,
    news_headlines: list[str],
) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {
            "error": "GEMINI_API_KEY not configured",
            "recommendation": "HOLD",
            "confidence": 0,
            "overall_summary": "API 키가 설정되지 않아 분석을 수행할 수 없습니다.",
        }

    client = genai.Client(api_key=api_key)
    prompt = _build_prompt(ticker, technical_data, financial_data, news_headlines)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    analysis = parse_analysis_response(response.text)
    analysis["ticker"] = ticker
    return analysis
