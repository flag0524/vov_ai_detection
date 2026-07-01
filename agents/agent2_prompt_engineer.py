# Agent 2: 상품 메타데이터와 모델 속성으로 Higgsfield 생성 프롬프트를 자동 작성
import os
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

SYSTEM_PROMPT = """당신은 럭셔리 패션 화보 프롬프트 전문가입니다.
입력된 상품 정보와 모델 정보를 바탕으로 Higgsfield AI 이미지 생성용 영문 프롬프트를 작성하세요.

규칙:
- 영문으로 작성
- 상품 원본(디자인·색상·패턴·로고)을 반드시 보존하도록 명시
- 모델 Soul ID 일관성을 위해 모델 속성을 프롬프트에 고정 토큰으로 포함
- 럭셔리 패션 매거진 화보 수준 (Vogue, Harper's Bazaar 스타일)
- 배경·조명·카메라 앵글 지정
- 200 토큰 이내

JSON으로만 응답:
{"prompt": "...", "negative_prompt": "..."}"""


def generate_photoshoot_prompt(product_meta: dict, model_attrs: dict, background: str = "Seoul luxury boutique") -> dict:
    """상품 메타 + 모델 속성 → Higgsfield 생성 프롬프트 딕셔너리를 반환한다.
    ANTHROPIC_API_KEY 미설정 시 스텁 프롬프트를 반환한다."""
    if _client is None:
        return {
            "prompt": f"Luxury fashion editorial photo, {model_attrs}, preserving original product design/color/pattern/logo, background: {background}, Vogue style",
            "negative_prompt": "altered product design, distorted logo",
            "stub": True,
        }

    user_msg = f"""상품 정보:
{product_meta}

모델 정보:
{model_attrs}

배경 선호: {background}"""

    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    import json
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"prompt": raw, "negative_prompt": ""}
