# 검수·재생성 라우터 (SCR-002) — 원본↔생성물 비교, 승인/재생성/폐기 상태 전이 (ADR-013)
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product, GenerationJob, Content
from app.services.quality import validate_generation
from app.api.pipeline import _download_generated

router = APIRouter(prefix="/review", tags=["review"])


def _original_url(image_ref: str) -> str:
    """로컬 상품 이미지 경로 → 브라우저에서 볼 수 있는 /storage URL (ADR-013 ⑤)."""
    if not image_ref:
        return None
    return f"/storage/uploads/{os.path.basename(image_ref)}"


def _scene_of(params: dict) -> str:
    """배경 표기. 구 스키마의 job은 background가 문자열로 저장돼 있어 둘 다 받는다."""
    bg = (params or {}).get("background")
    if isinstance(bg, dict):
        return bg.get("scene")
    return bg if isinstance(bg, str) else None


def _to_item(job: GenerationJob, product: Product) -> dict:
    refs = job.result_refs or {}
    quality = refs.get("quality") or {}
    return {
        "job_id": job.job_id,
        "product_id": job.product_id,
        "product_name": product.name if product else None,
        "category": product.category if product else None,
        "original_url": _original_url(product.image_ref if product else ""),
        "image_url": refs.get("image_url"),
        "ssim": quality.get("ssim_score"),
        "qa_status": refs.get("qa_status"),          # approved | manual_review | discarded
        "attempts": refs.get("attempts", 1),
        "history": refs.get("history", []),          # 재생성 회차별 이력
        "prompt": (job.params or {}).get("prompt"),
        "scene": _scene_of(job.params),
    }


@router.get("/jobs")
def list_review_jobs(status: str = None, db: Session = Depends(get_db)):
    """검수 대상 화보 목록. status로 필터 (manual_review | approved | discarded)."""
    jobs = (
        db.query(GenerationJob)
        .filter(GenerationJob.type == "image")
        .order_by(GenerationJob.created_at.desc())
        .all()
    )
    items = []
    for job in jobs:
        refs = job.result_refs or {}
        if status and refs.get("qa_status") != status:
            continue
        product = db.query(Product).filter(Product.product_id == job.product_id).first()
        items.append(_to_item(job, product))
    return {"items": items}


class DecisionRequest(BaseModel):
    action: str  # approve | discard


@router.patch("/jobs/{job_id}")
def decide(job_id: str, req: DecisionRequest, db: Session = Depends(get_db)):
    """승인/폐기 — 화보 job과 Content 상태를 함께 전이시킨다.
    approved만 배포 준비(라이브러리 발행)로 진입한다 (미승인 배포 금지의 데이터 강제)."""
    if req.action not in ("approve", "discard"):
        raise HTTPException(status_code=400, detail="action은 approve 또는 discard")

    job = db.query(GenerationJob).filter(GenerationJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="job not found")

    qa_status = "approved" if req.action == "approve" else "discarded"
    refs = dict(job.result_refs or {})
    refs["qa_status"] = qa_status
    job.result_refs = refs
    if req.action == "discard":
        job.status = "failed"

    content = (
        db.query(Content)
        .filter(Content.source_ref == job.product_id)
        .order_by(Content.created_at.desc())
        .first()
    )
    if content:
        content.status = qa_status

    db.commit()
    return {"job_id": job_id, "qa_status": qa_status,
            "content_status": content.status if content else None}


class RegenerateRequest(BaseModel):
    prompt: str = None  # 비우면 기존 프롬프트 그대로 재생성


@router.post("/jobs/{job_id}/regenerate")
def regenerate(job_id: str, req: RegenerateRequest, db: Session = Depends(get_db)):
    """프롬프트를 (선택적으로) 고쳐 화보를 다시 만든다. 크레딧을 소모한다.
    이력은 result_refs.history에 회차별로 쌓아 검수 화면에서 비교할 수 있게 한다."""
    job = db.query(GenerationJob).filter(GenerationJob.job_id == job_id).first()
    if not job or job.type != "image":
        raise HTTPException(status_code=404, detail="화보 job이 아닙니다")

    product = db.query(Product).filter(Product.product_id == job.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    from agents.agent3_fashion_model import generate_image

    params = job.params or {}
    prompt = (req.prompt or "").strip() or params.get("prompt", "")
    result = generate_image(
        prompt, "", product.image_ref or "", job.model_id,
        negative_prompt=params.get("negative_prompt", ""),
        model_key=params.get("model_key"),
    )

    refs = dict(job.result_refs or {})
    # 직전 결과를 이력으로 보존
    history = list(refs.get("history", []))
    if refs.get("image_url"):
        history.append({
            "image_url": refs["image_url"],
            "ssim": (refs.get("quality") or {}).get("ssim_score"),
            "at": datetime.now(timezone.utc).isoformat(),
        })

    # 실생성물을 내려받아 원본과 실제 비교 (스텁이면 원본끼리 비교로 폴백 — ADR-011)
    original = product.image_ref or ""
    regen_path = _download_generated(result["image_url"], str(uuid.uuid4()))
    quality = validate_generation(original, regen_path or original)
    refs.update({
        "image_url": result["image_url"],
        "quality": quality,
        "qa_status": quality["action"],
        "attempts": refs.get("attempts", 1) + 1,
        "history": history,
    })
    job.result_refs = refs

    new_params = dict(params)
    new_params["prompt"] = prompt
    job.params = new_params
    db.commit()

    return {
        "job_id": job_id,
        "image_url": result["image_url"],
        "ssim": quality.get("ssim_score"),
        "qa_status": refs["qa_status"],
        "attempts": refs["attempts"],
        "stub": result.get("stub", False),
    }
