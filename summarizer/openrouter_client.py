import json

from openai import OpenAI

from config import OPENROUTER_API_KEY

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Verified against https://openrouter.ai/api/v1/models at write time — OpenRouter's
# free tier rotates often (the previous list's llama-3.3-70b:free had already been
# pulled), so if summarize starts failing, re-check that list before assuming a bug.
MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "openai/gpt-oss-20b:free",
]

BASE_MAX_TOKENS = 400
PER_SIGNAL_TOKENS = 300
MAX_TOKENS_CAP = 2000

SYSTEM_PROMPT = """당신은 중장기 보유 투자자를 위한 애널리스트입니다.
아래로 전달되는 "신호" 목록은 규칙 엔진이 이미 계산과 판정을 끝낸 결과입니다.
당신의 역할은 서식을 채우는 것이 아니라, 각 신호가 왜 중요하고 무엇을 확인해야 하는지 해석하는 것입니다.

규칙:
- 숫자(%, 배수, 가격 등)는 반드시 전달된 신호 데이터에 있는 것만 인용한다. 새로운 숫자를 계산하거나 지어내지 않는다.
- 진입가·손절가 등 단기 매매 신호는 제시하지 않는다. 이 서비스는 중장기 보유자를 대상으로 하며, 그런 데이터 자체가 주어지지 않는다.
- related_news가 있으면 맥락으로 참고하되, 기사에 없는 사실을 지어내지 않는다.
- 신호가 있는 종목만, 종목별로 2~3문장씩 작성한다. "종목명 — 해설" 형식.
- 신호가 여러 개인 종목은 함께 묶어서 설명해도 된다."""


def interpret_signals(signals: list) -> str:
    """Interpret already-detected signals. Numbers can't be invented here —
    they're not computed in this call, only explained.
    """
    if not signals:
        return ""

    max_tokens = min(MAX_TOKENS_CAP, BASE_MAX_TOKENS + PER_SIGNAL_TOKENS * len(signals))
    user_content = json.dumps(signals, ensure_ascii=False, indent=2)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"다음 신호들을 해설해주세요:\n\n{user_content}"},
    ]
    last_err = None
    for model in MODELS:
        try:
            response = client.chat.completions.create(
                model=model, max_tokens=max_tokens, messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            last_err = e
            continue
    raise RuntimeError(f"모든 모델 실패: {last_err}")
