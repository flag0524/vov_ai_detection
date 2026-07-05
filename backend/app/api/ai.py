# AI 모델 생성·이미지·영상 생성 API 라우터
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import AIModel, GenerationJob, Product

router = APIRouter(prefix="/ai", tags=["ai"])


class ModelCreateRequest(BaseModel):
    hair_style: str = "straight black"
    age: str = "late 20s"
    mood: str = "elegant"
    fashion_style: str = "luxury"
    reference_image_path: str = ""


class ImageGenerateRequest(BaseModel):
    product_id: str
    model_id: str
    background: str = "Seoul luxury boutique"


class VideoGenerateRequest(BaseModel):
    image_url: str
    duration_sec: int = 10
    camera_motion: str = "dolly_in"


@router.post("/model/create")
def create_model(req: ModelCreateRequest, db: Session = Depends(get_db)):
    from agents.agent3_fashion_model import create_soul_id

    soul_result = create_soul_id(
        model_attrs=req.model_dump(),
        reference_image_path=req.reference_image_path,
    )

    model = AIModel(
        model_id=str(uuid.uuid4()),
        soul_reference_id=soul_result["soul_reference_id"],
        hair_style=req.hair_style,
        age=req.age,
        mood=req.mood,
        fashion_style=req.fashion_style,
    )
    db.add(model)
    db.commit()
    db.refresh(model)

    return {
        "model_id": model.model_id,
        "soul_reference_id": model.soul_reference_id,
        "stub": soul_result.get("stub", False),
    }


@router.post("/image/generate")
def generate_image(req: ImageGenerateRequest, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    ai_model = db.query(AIModel).filter(AIModel.model_id == req.model_id).first()
    if not ai_model:
        raise HTTPException(status_code=404, detail="model not found")

    from agents.agent2_prompt_engineer import generate_photoshoot_prompt
    from agents.agent3_fashion_model import generate_image as hf_generate

    # 상품 정보는 업로드 시 입력값 사용 (ADR-012, Vision 분석 폐기)
    product_meta = {
        k: v
        for k, v in {
            "product_name": product.name,
            "category": product.category,
            "color": product.color,
            "material": product.material,
            "style": product.style,
        }.items()
        if v
    }

    model_attrs = {
        "hair_style": ai_model.hair_style,
        "age": ai_model.age,
        "mood": ai_model.mood,
        "fashion_style": ai_model.fashion_style,
    }
    prompt_result = generate_photoshoot_prompt(product_meta, model_attrs, req.background)

    image_result = hf_generate(
        prompt=prompt_result["prompt"],
        soul_reference_id=ai_model.soul_reference_id,
        product_image_path=product.image_ref or "",
        model_id=req.model_id,
    )

    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        type="image",
        product_id=req.product_id,
        model_id=req.model_id,
        status="done",
        params={"prompt": prompt_result["prompt"], "background": req.background},
        result_refs={"image_url": image_result["image_url"]},
    )
    db.add(job)
    db.commit()

    return {
        "job_id": job.job_id,
        "status": "done",
        "image_url": image_result["image_url"],
        "prompt": prompt_result["prompt"],
        "stub": image_result.get("stub", False),
    }


@router.post("/video/generate")
def generate_video(req: VideoGenerateRequest, db: Session = Depends(get_db)):
    from agents.agent4_video_creator import generate_video as hf_video

    video_result = hf_video(
        image_url=req.image_url,
        duration_sec=req.duration_sec,
        camera_motion=req.camera_motion,
    )

    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        type="video",
        status="done",
        params={"image_url": req.image_url, "duration_sec": req.duration_sec},
        result_refs={"video_url": video_result["video_url"]},
    )
    db.add(job)
    db.commit()

    return {
        "job_id": job.job_id,
        "status": "done",
        "video_url": video_result["video_url"],
        "stub": video_result.get("stub", False),
    }
