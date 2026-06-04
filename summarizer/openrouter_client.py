import json
from openai import OpenAI
from config import OPENROUTER_API_KEY

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-4-31b-it:free",
    "moonshotai/kimi-k2.6:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

SYSTEM_PROMPT = """당신은 한국과 미국 주식시장 전문 애널리스트입니다.
매일 아침 투자자에게 핵심 시황을 요약하고 오늘의 매매 전략을 제시합니다.

출력 형식:
━━━━━━━━━━━━━━━━━━━━
📊 모닝 브리핑 — {오늘날짜}
━━━━━━━━━━━━━━━━━━━━

① 미국 시장 요약
(전일 S&P500·NASDAQ·DOW 등락, VIX 수준, 주요 섹터 흐름, USD/KRW)

② 한국 시장 전망
(KOSPI·KOSDAQ 예상 흐름, 주목 업종)

③ 오늘의 핵심 이슈
(미국 경제지표 발표 일정, 주요 뉴스 3~5개 요약)

④ 매매 포인트
(구체적 전략 + 손절 기준 반드시 포함)
━━━━━━━━━━━━━━━━━━━━
⚠️ 본 내용은 투자 참고용이며 투자 결정의 책임은 본인에게 있습니다.

규칙:
- 전체 800토큰 이내
- 숫자는 구체적으로 (% 포함)
- 매매 포인트는 반드시 손절 기준 포함"""


def summarize(data: dict) -> str:
    user_content = json.dumps(data, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"다음 데이터를 기반으로 오늘의 모닝 브리핑을 작성해주세요:\n\n{user_content}"},
    ]
    last_err = None
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model, max_tokens=900, messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"모든 모델 실패: {last_err}")
