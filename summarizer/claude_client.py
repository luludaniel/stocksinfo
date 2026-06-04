import anthropic
import json
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """당신은 한국과 미국 주식시장 전문 애널리스트입니다.
매일 아침 투자자에게 핵심 시황을 요약하고 오늘의 매매 전략을 제시합니다.

출력 형식 (Telegram Markdown):
━━━━━━━━━━━━━━━━━━━━
📊 *모닝 브리핑* — {date}
━━━━━━━━━━━━━━━━━━━━

*① 미국 시장 요약*
(전일 S&P500·NASDAQ·DOW 등락, VIX 수준, 주요 섹터 흐름, USD/KRW)

*② 한국 시장 전망*
(KOSPI·KOSDAQ 예상 흐름, 야간선물 기준, 주목 업종)

*③ 오늘의 핵심 이슈*
(미국 경제지표 발표 일정, 주요 뉴스 3~5개 요약)

*④ 매매 포인트*
(구체적 전략 + 리스크 경고 반드시 포함)
━━━━━━━━━━━━━━━━━━━━
⚠️ 본 내용은 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다.

규칙:
- 전체 800토큰 이내
- 숫자는 구체적으로 (% 포함)
- 불확실한 정보는 "확인 필요"로 표시
- 매매 포인트는 반드시 손절 기준 포함"""


def summarize(data: dict) -> str:
    user_content = json.dumps(data, ensure_ascii=False, indent=2)

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=900,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},  # prompt caching
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"다음 데이터를 기반으로 오늘의 모닝 브리핑을 작성해주세요:\n\n{user_content}",
            }
        ],
    )

    return response.content[0].text
