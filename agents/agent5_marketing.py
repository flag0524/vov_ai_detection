# Agent 5: 상품 정보로 SNS 게시글·해시태그·광고 카피를 규칙 기반 템플릿으로 생성 (ADR-012)

# 카테고리 → 카테고리 해시태그 매핑
_CATEGORY_TAGS = {
    "원피스": ["#원피스", "#원피스코디"],
    "재킷": ["#재킷", "#아우터"],
    "코트": ["#코트", "#아우터"],
    "가방": ["#가방", "#백스타그램"],
    "바지": ["#팬츠", "#데일리팬츠"],
    "스커트": ["#스커트", "#스커트코디"],
    "블라우스": ["#블라우스", "#오피스룩"],
}

_BASE_TAGS = ["#제이블랑", "#JBLANC", "#여성패션", "#데일리룩", "#OOTD", "#패션스타그램", "#신상", "#럭셔리패션"]


def generate_sns_content(product_meta: dict, channel: str = "instagram") -> dict:
    """상품 정보로 SNS 게시글·해시태그·광고 카피를 템플릿으로 조립한다.
    외부 API 없이 결정적으로 동작한다 (ADR-012: Anthropic 미사용)."""
    name = product_meta.get("product_name") or product_meta.get("name") or "신상품"
    category = product_meta.get("category") or ""
    color = product_meta.get("color") or ""
    style = product_meta.get("style") or ""

    desc = " ".join(p for p in (color, category) if p) or "새로운 컬렉션"

    caption = (
        f"✨ {name} ✨\n"
        f"제이블랑이 제안하는 {desc}"
        f"{f', {style} 무드로 완성했습니다' if style else '를 만나보세요'}.\n"
        f"지금 프로필 링크에서 확인하세요 💫"
    )

    hashtags = list(_BASE_TAGS)
    hashtags += _CATEGORY_TAGS.get(category, [])
    if style and f"#{style}" not in hashtags:
        hashtags.append(f"#{style}룩")

    ad_copy = f"{desc}, 당신의 특별한 순간" if len(desc) <= 12 else "당신의 특별한 순간"

    return {
        "caption": caption,
        "hashtags": hashtags,
        "ad_copy": ad_copy,
        "channel": channel,
    }
