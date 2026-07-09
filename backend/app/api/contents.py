# 생성 완료 콘텐츠 목록 조회 라우터 (카테고리별 라이브러리, SCR-004)
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product, GenerationJob, Content

router = APIRouter(prefix="/contents", tags=["contents"])


@router.get("")
def list_contents(category: str = None, db: Session = Depends(get_db)):
    """생성 이력이 있는 상품을 카테고리별로 조회한다.
    각 상품의 최신 화보 이미지·릴스 영상·SNS 카피·검수 상태를 묶어 반환한다."""
    q = db.query(Product).order_by(Product.created_at.desc())
    if category:
        q = q.filter(Product.category == category)

    items = []
    for p in q.all():
        img = (
            db.query(GenerationJob)
            .filter(GenerationJob.product_id == p.product_id, GenerationJob.type == "image")
            .order_by(GenerationJob.created_at.desc())
            .first()
        )
        if not img:
            continue  # 생성 이력 없는 상품은 라이브러리에 노출하지 않음
        vid = (
            db.query(GenerationJob)
            .filter(GenerationJob.product_id == p.product_id, GenerationJob.type == "video")
            .order_by(GenerationJob.created_at.desc())
            .first()
        )
        content = (
            db.query(Content)
            .filter(Content.source_ref == p.product_id)
            .order_by(Content.created_at.desc())
            .first()
        )
        img_refs = img.result_refs or {}
        vid_refs = (vid.result_refs or {}) if vid else {}
        items.append(
            {
                "product_id": p.product_id,
                "name": p.name,
                "category": p.category,
                "image_url": img_refs.get("image_url"),
                "video_url": vid_refs.get("video_url"),
                "qa_status": img_refs.get("qa_status"),
                "ssim": (img_refs.get("quality") or {}).get("ssim_score"),
                "caption": content.caption if content else None,
                "hashtags": content.hashtags if content else [],
                "ad_copy": content.ad_copy if content else None,
            }
        )
    return {"items": items}
