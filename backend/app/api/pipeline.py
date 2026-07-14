# 단일 엔드포인트로 전체 파이프라인(분석→이미지→영상→SNS)을 실행하는 라우터
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product, AIModel, GenerationJob, Content
from app.services.quality import validate_generation

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

RESULTS_DIR = os.path.join(os.getenv("STORAGE_LOCAL_DIR", "../storage"), "results")


def _download_generated(image_url: str, job_key: str) -> str | None:
    """실생성 이미지를 storage/results/에 내려받아 로컬 경로를 반환한다.
    스텁 URL이거나 다운로드 실패 시 None (SSIM은 원본끼리 비교로 폴백)."""
    if image_url.startswith("https://stub."):
        return None
    try:
        import httpx
        resp = httpx.get(image_url, timeout=60)
        resp.raise_for_status()
        os.makedirs(RESULTS_DIR, exist_ok=True)
        path = os.path.join(RESULTS_DIR, f"{job_key}.jpg")
        with open(path, "wb") as f:
            f.write(resp.content)
        return path
    except Exception:
        return None


class BackgroundSpec(BaseModel):
    # SCREEN_DESIGN §2.6 — 배경/씨 선택 (프리셋 키 + 커스텀 텍스트)
    preset: str = None
    custom: str = None


class PipelineRequest(BaseModel):
    product_id: str
    model_id: str = None
    background: BackgroundSpec = None
    # SCREEN_DESIGN §2.5 #5 — 자연스러운 동작 연출 (릴스 카메라 워킹)
    camera_motion: str = "dolly_in"


@router.post("/run")
def run_full_pipeline(req: PipelineRequest, db: Session = Depends(get_db)):
    """상품 ID 하나로 화보·영상·SNS 카피를 자동 생성하는 E2E 파이프라인."""
    start_time = time.time()
    product = db.query(Product).filter(Product.product_id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    from agents.agent2_prompt_engineer import generate_photoshoot_prompt, resolve_background
    from agents.agent3_fashion_model import create_soul_id, generate_image
    from agents.agent4_video_creator import generate_video
    from agents.agent5_marketing import generate_sns_content

    # 배경/씨: 프리셋 키/커스텀 텍스트를 씨 문구로 해석 (모델·상품은 고정, 배경만 변경)
    bg = req.background or BackgroundSpec()
    scene = resolve_background(bg.preset, bg.custom)

    # Step 1: 상품 정보 — 업로드 시 담당자가 입력한 값 사용 (ADR-012, Vision 분석 폐기)
    image_path = product.image_ref or ""
    product_meta = {
        k: v
        for k, v in {
            "product_name": product.name,
            "category": product.category,
            "color": product.color,
            "material": product.material,
            "silhouette": product.silhouette,
            "season": product.season,
            "style": product.style,
            "target_customer": product.target_customer,
        }.items()
        if v
    }

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

    # Step 3: 프롬프트 + 이미지 생성 (1회)
    prompt_result = generate_photoshoot_prompt(product_meta, model_attrs, scene)
    image_result = generate_image(
        prompt_result["prompt"], ai_model.soul_reference_id, image_path, ai_model.model_id,
        negative_prompt=prompt_result["negative_prompt"],
    )

    # Step 4: 품질 검증 — SSIM은 정보성 점수 (ADR-011, 2026-07-05 사용자 결정)
    # 실생성물은 다운로드해 원본과 실제 비교하고, 미달 시 manual_review로 표시만 한다
    # (자동 재생성/failed 없음 — 구도 차이로 하드 게이트가 항상 탈락해 크레딧만 소모).
    job_key = str(uuid.uuid4())
    generated_path = _download_generated(image_result["image_url"], job_key)
    quality = validate_generation(image_path, generated_path or image_path)
    attempts = 1

    # Step 5: 영상 생성 (카메라 동작 = 자연스러운 연출 제어)
    video_result = generate_video(image_url=image_result["image_url"], camera_motion=req.camera_motion)

    # Step 6: SNS 카피
    sns_result = generate_sns_content(product_meta)

    processing_time_sec = round(time.time() - start_time, 3)

    # DB 저장
    img_job = GenerationJob(
        job_id=job_key, type="image", product_id=product.product_id,
        model_id=ai_model.model_id, status="done",
        params={"prompt": prompt_result["prompt"], "background": {"preset": bg.preset, "custom": bg.custom, "scene": scene}},
        result_refs={
            "image_url": image_result["image_url"],
            "local_path": generated_path,
            "quality": quality,
            "qa_status": quality["action"],  # approved | manual_review (ADR-011)
            "attempts": attempts,
        },
    )
    vid_job = GenerationJob(
        job_id=str(uuid.uuid4()), type="video", product_id=product.product_id,
        model_id=ai_model.model_id, status="done",
        result_refs={"video_url": video_result["video_url"], "camera_motion": req.camera_motion},
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
        "regeneration_attempts": attempts,
        "processing_time_sec": processing_time_sec,
        "video_url": video_result["video_url"],
        "camera_motion": req.camera_motion,
        "sns": sns_result,
        "stubs": {
            "image": image_result.get("stub", False),
            "video": video_result.get("stub", False),
        },
    }
