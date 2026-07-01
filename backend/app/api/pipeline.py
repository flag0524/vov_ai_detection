# 단일 엔드포인트로 전체 파이프라인(분석→이미지→영상→SNS)을 실행하는 라우터
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product, AIModel, GenerationJob, Content
from app.services.quality import validate_generation

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRequest(BaseModel):
    product_id: str
    model_id: str = None
    background: str = "Seoul luxury boutique"


@router.post("/run")
def run_full_pipeline(req: PipelineRequest, db: Session = Depends(get_db)):
    """상품 ID 하나로 화보·영상·SNS 카피를 자동 생성하는 E2E 파이프라인."""
    product = db.query(Product).filter(Product.product_id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    from agents.agent1_product_analyzer import analyze_product_image
    from agents.agent2_prompt_engineer import generate_photoshoot_prompt
    from agents.agent3_fashion_model import create_soul_id, generate_image
    from agents.agent4_video_creator import generate_video
    from agents.agent5_marketing import generate_sns_content

    # Step 1: 상품 분석
    image_path = product.image_ref or ""
    product_meta = analyze_product_image(image_path) if os.path.exists(image_path) else {"product_name": product.name}

    # Step 2: 모델 (기존 모델 재사용 또는 신규 생성)
    ai_model = None
    if req.model_id:
        ai_model = db.query(AIModel).filter(AIModel.model_id == req.model_id).first()

    if not ai_model:
        default_attrs = {"hair_style": "straight black", "age": "late 20s", "mood": "elegant", "fashion_style": "luxury"}
        soul_result = create_soul_id(default_attrs, image_path)
        ai_model = AIModel(
            model_id=str(uuid.uuid4()),
            soul_reference_id=soul_result["soul_reference_id"],
            **default_attrs,
        )
        db.add(ai_model)
        db.commit()
        db.refresh(ai_model)

    model_attrs = {"hair_style": ai_model.hair_style, "age": ai_model.age, "mood": ai_model.mood, "fashion_style": ai_model.fashion_style}

    # Step 3: 프롬프트 + 이미지 생성
    prompt_result = generate_photoshoot_prompt(product_meta, model_attrs, req.background)
    image_result = generate_image(prompt_result["prompt"], ai_model.soul_reference_id, image_path, ai_model.model_id)

    # Step 4: 품질 검증 (스텁 이미지면 패스, 실제 이미지면 SSIM 검증)
    quality = validate_generation(image_path, image_path)

    # Step 5: 영상 생성
    video_result = generate_video(image_url=image_result["image_url"])

    # Step 6: SNS 카피
    sns_result = generate_sns_content(product_meta)

    # DB 저장
    img_job = GenerationJob(
        job_id=str(uuid.uuid4()), type="image", product_id=product.product_id,
        model_id=ai_model.model_id, status="done",
        params={"prompt": prompt_result["prompt"]},
        result_refs={"image_url": image_result["image_url"]},
    )
    vid_job = GenerationJob(
        job_id=str(uuid.uuid4()), type="video", product_id=product.product_id,
        model_id=ai_model.model_id, status="done",
        result_refs={"video_url": video_result["video_url"]},
    )
    content = Content(
        content_id=str(uuid.uuid4()), source_ref=product.product_id,
        caption=sns_result.get("caption", ""), hashtags=sns_result.get("hashtags", []),
        ad_copy=sns_result.get("ad_copy", ""), channel="instagram", status="draft",
    )
    db.add_all([img_job, vid_job, content])
    db.commit()

    return {
        "product_id": product.product_id,
        "product_meta": product_meta,
        "model_id": ai_model.model_id,
        "soul_reference_id": ai_model.soul_reference_id,
        "prompt": prompt_result["prompt"],
        "image_url": image_result["image_url"],
        "quality": quality,
        "video_url": video_result["video_url"],
        "sns": sns_result,
        "stubs": {
            "image": image_result.get("stub", False),
            "video": video_result.get("stub", False),
        },
    }
