# Agent 5: 상품 정보와 생성 이미지 기반으로 SNS 게시글·해시태그·광고 카피를 생성
import os
import json
import anthropic

_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """당신은 제이블랑(JBLANC) 브랜드 SNS 마케팅 전문가입니다.
입력된 상품 정보를 바탕으로 인스타그램 콘텐츠를 작성하세요.

브랜드 톤: 럭셔리하고 감각적이며 여성스러운 한국 패션 브랜드.

JSON으로만 응답:
{
  "caption": "인스타그램 게시글 문구 (이모지 포함, 2~3문장)",
  "hashtags": ["#제이블랑", "#여성패션", ...최소 8개],
  "ad_copy": "광고 카피 한 줄 (임팩트 있게, 20자 이내)"
}"""


def generate_sns_content(product_meta: dict, channel: str = "instagram") -> dict:
    """상품 메타데이터로 SNS 게시글·해시태그·광고 카피를 생성한다."""
    user_msg = f"채널: {channel}\n상품 정보:\n{json.dumps(product_meta, ensure_ascii=False, indent=2)}"

    message = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    raw = message.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"caption": raw, "hashtags": ["#제이블랑"], "ad_copy": "", "parse_error": True}
