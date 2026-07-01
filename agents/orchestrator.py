# 전체 파이프라인 오케스트레이터: Agent 1→2→3→4→5 순차 실행
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.agent1_product_analyzer import analyze_product_image
from agents.agent2_prompt_engineer import generate_photoshoot_prompt
from agents.agent3_fashion_model import create_soul_id, generate_image
from agents.agent4_video_creator import generate_video
from agents.agent5_marketing import generate_sns_content


def run_pipeline(
    product_image_path: str,
    model_attrs: dict,
    soul_reference_id: str = None,
    background: str = "Seoul luxury boutique",
) -> dict:
    """상품 이미지 하나로 화보·영상·SNS 카피를 모두 생성하고 결과를 반환한다."""

    # Phase 1: 상품 분석
    product_meta = analyze_product_image(product_image_path)

    # Phase 1: Soul ID (신규 모델이면 학습, 기존이면 재사용)
    if not soul_reference_id:
        soul_result = create_soul_id(model_attrs, product_image_path)
        soul_reference_id = soul_result["soul_reference_id"]
    else:
        soul_result = {"soul_reference_id": soul_reference_id, "reused": True}

    # Phase 2: 프롬프트 생성
    prompt_result = generate_photoshoot_prompt(product_meta, model_attrs, background)

    # Phase 2: 이미지 생성
    image_result = generate_image(
        prompt=prompt_result["prompt"],
        soul_reference_id=soul_reference_id,
        product_image_path=product_image_path,
        model_id=model_attrs.get("model_id", "MODEL_JBLANC_001"),
    )

    # Phase 3: 영상 생성
    video_result = generate_video(image_url=image_result["image_url"])

    # Phase 4: SNS 콘텐츠
    sns_result = generate_sns_content(product_meta)

    return {
        "product_meta": product_meta,
        "soul_reference_id": soul_reference_id,
        "soul_stub": soul_result.get("stub", False),
        "prompt": prompt_result,
        "image": image_result,
        "video": video_result,
        "sns": sns_result,
    }
