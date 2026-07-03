# Agent 1: 상품 이미지를 Vision 분석해 카테고리·속성 메타데이터를 추출
import os
import base64
import json
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

_STUB_RESULT = {
    "product_name": "STUB 원피스",
    "category": "원피스",
    "color": "블랙",
    "material": "폴리에스터",
    "silhouette": "A라인",
    "season": "사계절",
    "style": "럭셔리",
    "target_customer": "20~30대 여성",
    "stub": True,
}

SYSTEM_PROMPT = """당신은 패션 상품 분석 전문가입니다.
상품 이미지를 보고 다음 JSON 형식으로만 응답하세요. 다른 텍스트는 출력하지 마세요.

{
  "product_name": "상품명 추정",
  "category": "원피스|재킷|코트|가방|바지|스커트|블라우스|기타",
  "color": "주요 색상",
  "material": "소재 추정",
  "silhouette": "실루엣 형태",
  "season": "봄|여름|가을|겨울|사계절",
  "style": "캐주얼|오피스|럭셔리|스트릿|빈티지|기타",
  "target_customer": "타깃 고객 설명"
}"""


def analyze_product_image(image_path: str) -> dict:
    """상품 이미지 파일 경로를 받아 메타데이터 딕셔너리를 반환한다.
    ANTHROPIC_API_KEY 미설정 시 스텁 메타데이터를 반환한다."""
    if _client is None:
        return dict(_STUB_RESULT)

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    media_type_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
    media_type = media_type_map.get(ext, "image/jpeg")

    try:
        message = _client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                        {"type": "text", "text": "이 패션 상품 이미지를 분석해 주세요."},
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        # 크레딧 부족 등 API 실패 시 파이프라인을 죽이지 않고 스텁으로 강등
        return {**_STUB_RESULT, "reason": str(e)}

    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # JSON 파싱 실패 시 원문 포함해 반환
        return {"raw": raw, "parse_error": True}
