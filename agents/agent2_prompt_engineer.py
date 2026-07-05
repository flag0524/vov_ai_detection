# Agent 2: 상품 메타데이터와 모델 속성으로 Higgsfield 생성 프롬프트를 자동 작성
import os
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# PRD FR-7 / TRD §5 — 동작·표정 자연스러움(Naturalness) 지시어 (이미지)
NATURALNESS_PROMPT = (
    "Expression: natural relaxed expression, soft gaze, subtle confident smile, "
    "lifelike facial detail. "
    "Pose: natural fashion pose, anatomically correct body, natural weight "
    "distribution, relaxed hands, accurate fingers."
)

# PRD FR-7 / TRD §5 — Naturalness Negative Prompt (이미지)
NATURALNESS_NEGATIVE = (
    "stiff pose, unnatural facial expression, frozen face, awkward smile, "
    "dead eyes, asymmetric distorted face, broken joints, distorted fingers, "
    "unnatural neck angle, uncanny valley"
)

SYSTEM_PROMPT = f"""당신은 럭셔리 패션 화보 프롬프트 전문가입니다.
입력된 상품 정보와 모델 정보를 바탕으로 Higgsfield AI 이미지 생성용 영문 프롬프트를 작성하세요.

규칙:
- 영문으로 작성
- 상품 원본(디자인·색상·패턴·로고)을 반드시 보존하도록 명시
- 모델 Soul ID 일관성을 위해 모델 속성을 프롬프트에 고정 토큰으로 포함
- 럭셔리 패션 매거진 화보 수준 (Vogue, Harper's Bazaar 스타일)
- 배경·조명·카메라 앵글 지정
- 자연스러움 지시어를 prompt에 반드시 포함: {NATURALNESS_PROMPT}
- negative_prompt에 다음 항목을 반드시 포함: {NATURALNESS_NEGATIVE}
- 250 토큰 이내

JSON으로만 응답:
{{"prompt": "...", "negative_prompt": "..."}}"""


def generate_photoshoot_prompt(product_meta: dict, model_attrs: dict, background: str = "Seoul luxury boutique") -> dict:
    """상품 메타 + 모델 속성 → Higgsfield 생성 프롬프트 딕셔너리를 반환한다.
    ANTHROPIC_API_KEY 미설정 또는 API 실패 시 스텁 프롬프트를 반환한다."""
    def _stub(reason: str = "") -> dict:
        result = {
            "prompt": (
                f"Luxury fashion editorial photo, {model_attrs}, preserving original "
                f"product design/color/pattern/logo, background: {background}, "
                f"Vogue style. {NATURALNESS_PROMPT}"
            ),
            "negative_prompt": f"altered product design, distorted logo, {NATURALNESS_NEGATIVE}",
            "stub": True,
        }
        if reason:
            result["reason"] = reason
        return result

    if _client is None:
        return _stub()

    user_msg = f"""상품 정보:
{product_meta}

모델 정보:
{model_attrs}

배경 선호: {background}"""

    try:
        message = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as e:
        # 크레딧 부족 등 API 실패 시 파이프라인을 죽이지 않고 스텁으로 강등
        return _stub(reason=str(e))

    import json
    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"prompt": raw, "negative_prompt": ""}
