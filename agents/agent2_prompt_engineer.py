# Agent 2: 상품 정보와 모델 속성으로 Higgsfield 생성 프롬프트를 규칙 기반 템플릿으로 작성 (ADR-012)
import os

# 생성물에 들어갈 브랜드명. ADR-014 기준 콘텐츠는 JBLANC 계정용이고 VOV는 벤치마크(주입 금지)라
# 기본값을 JBLANC로 둔다. 바꾸려면 이 상수/환경변수만 교체.
BRAND_NAME = os.getenv("JBLANC_BRAND_NAME", "JBLANC")

# PRD FR-7 / TRD §5 — 동작·표정 자연스러움(Naturalness) 지시어 (이미지)
NATURALNESS_PROMPT = (
    "Expression: natural relaxed expression, soft gaze, subtle confident smile, "
    "lifelike facial detail. "
    "Pose: natural fashion pose, anatomically correct body, natural weight "
    "distribution, relaxed hands, accurate fingers."
)

# 동작(Action) — 자연스러운 보행. 발 미끄러짐(sliding) 방지는 프롬프트+네거티브로만 가능
ACTION_PROMPT = (
    "Action: naturally walking towards the camera, realistic human gait, "
    "fluid leg movement, feet firmly planted on the ground, no sliding effect."
)

# 체형 비율(Appearance) — 인위적으로 길어 보이는 8등신 과장을 막고 실제 체형으로 고정
# (물리 엔진 보정 레이어는 생성 API 위에 만들 수 없으므로 프롬프트/네거티브 + 검수로 관리)
PROPORTION_PROMPT = (
    "Appearance: realistic Korean adult female body proportions, natural head-to-body ratio "
    "(about 7 heads tall), average height for a fashion model (not excessively tall), "
    "natural leg length, true-to-life shoulder width, high-end editorial look."
)

# 기술(Technical) — 실사 화보 품질. 'AI스러움' 제거
TECHNICAL_PROMPT = (
    "Technical: 8k resolution, shot on 35mm lens, cinematic lighting, photorealistic, "
    "high-quality editorial photography, Instagram-ready aesthetic, "
    "extreme detail on fabric texture, NOT CGI looking."
)

# PRD FR-7 / TRD §5 — Naturalness Negative Prompt (이미지) + 비율/보행/AI아티팩트 방지
NATURALNESS_NEGATIVE = (
    "stiff pose, unnatural facial expression, frozen face, awkward smile, "
    "dead eyes, asymmetric distorted face, broken joints, distorted fingers, "
    "unnatural neck angle, uncanny valley, "
    "distorted limbs, unnatural walking, sliding feet, floating, "
    "exaggerated body proportions, unnaturally long legs, stretched body, "
    "distorted head-to-body ratio, doll-like proportions"
)

# TRD §5 — 상품 원본 보존 + 품질 공통 지시어
_BASE_NEGATIVE = (
    "different face, identity change, bad anatomy, extra fingers, unnatural body, "
    "plastic skin, AI generated look, AI artifacts, artificial, cartoon, anime, "
    "low quality, messy background, "
    "distorted clothing, wrong product details, altered product design, distorted logo"
)

# SCREEN_DESIGN §2.6 — 배경/씨 프리셋 (모델·상품 고정, 배경만 자유 변수)
# 프리셋 키 → 화보 프롬프트에 주입할 씨 문구. 신규 프리셋은 여기만 추가한다.
# summer_* 계열은 '미니멀한 선 · 모던 스타일' 여름 테마 (VOV 벤치마크 톤)
PRESET_SCENES = {
    "studio_white": "clean white seamless studio backdrop, professional softbox lighting",
    "city_street": "modern urban city street, contemporary architecture, natural daylight",
    "cafe": "cozy cafe interior, warm ambient light, softly blurred background",
    "nature": "outdoor natural setting with greenery, soft natural daylight, golden hour",
    "minimal_color": "minimal solid color background with soft gradient, studio lighting",
    "luxury_terrace": (
        "modern luxury rooftop terrace in the city, minimal clean lines, summer daylight, "
        "potted greenery, warm sunlight and soft shadows"
    ),
    "mediterranean": (
        "Mediterranean minimal white architecture, whitewashed walls and clean geometric lines, "
        "bright summer sunlight, deep blue sky"
    ),
    "resort_poolside": (
        "minimal modern resort poolside, calm water reflections, clean architectural lines, "
        "bright summer daylight"
    ),
    "stone_courtyard": (
        "white stone courtyard with minimal modern architecture, crisp summer shadows, "
        "quiet contemporary atmosphere"
    ),
    "concrete_architecture": (
        "sophisticated sun-drenched modern architectural space, midsummer atmosphere, "
        "soft natural shadows, minimalist concrete texture, clean geometric lines"
    ),
}
_DEFAULT_PRESET = "studio_white"


def resolve_background(preset: str = None, custom: str = None) -> str:
    """배경 프리셋 키/커스텀 텍스트를 화보 프롬프트용 씨 문구로 해석한다.
    우선순위: 커스텀(비어있지 않으면) > 프리셋 매핑 > 기본값(studio_white)."""
    if custom and custom.strip():
        return custom.strip()
    if preset and preset in PRESET_SCENES:
        return PRESET_SCENES[preset]
    return PRESET_SCENES[_DEFAULT_PRESET]


def generate_photoshoot_prompt(product_meta: dict, model_attrs: dict, background: str = "Seoul luxury boutique") -> dict:
    """상품 정보 + 모델 속성 → Higgsfield 생성 프롬프트를 템플릿으로 조립한다.
    외부 API 없이 결정적으로 동작한다 (ADR-012: Anthropic 미사용)."""
    product_parts = [
        str(product_meta.get(k))
        for k in ("color", "material", "category", "silhouette", "style")
        if product_meta.get(k)
    ]
    product_desc = " ".join(product_parts) if product_parts else "fashion product"
    product_name = product_meta.get("product_name") or product_meta.get("name") or ""

    model_parts = [
        str(model_attrs.get(k))
        for k in ("age", "hair_style", "mood", "fashion_style")
        if model_attrs.get(k)
    ]
    model_desc = ", ".join(model_parts) if model_parts else "elegant Korean fashion model"

    # flux-2에 상품 이미지를 image_urls 참조로 넣으므로(ADR-015), 프롬프트도 "참조 이미지의 그 옷"을
    # 명시해 상품 보존을 강제한다 (실증에서 이 문구로 원본 재현 성공).
    # 구조: Subject → Action → Appearance → Background → Technical (사용자 지정 템플릿)
    prompt = (
        f"Subject: a professional Korean female fashion model ({model_desc}) for {BRAND_NAME}, "
        f"consistent face and body shape, wearing the exact garment shown in the reference image"
        f"{f' ({product_name})' if product_name else ''} — {product_desc}, "
        f"minimal lines and modern style, "
        f"preserving its design, color, pattern, fabric texture and logo exactly. "
        f"{ACTION_PROMPT} "
        f"{PROPORTION_PROMPT} "
        f"Background: {background}. "
        f"{TECHNICAL_PROMPT} "
        f"{NATURALNESS_PROMPT}"
    )

    return {
        "prompt": prompt,
        "negative_prompt": f"{_BASE_NEGATIVE}, {NATURALNESS_NEGATIVE}",
    }
