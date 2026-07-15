# 생성 완료 콘텐츠 목록 조회 라우터 (카테고리별 라이브러리, SCR-004)
import io
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product, GenerationJob, Content
from app.services.export import export_bytes, FORMATS

router = APIRouter(prefix="/contents", tags=["contents"])

RESULTS_DIR = os.path.join(os.getenv("STORAGE_LOCAL_DIR", "../storage"), "results")


def _local_source(refs: dict) -> str:
    """화보 이미지의 로컬 파일 경로. 이미 내려받았으면 그대로, 아니면 image_url을 받아온다."""
    local = refs.get("local_path")
    if local and os.path.exists(local):
        return local
    url = refs.get("image_url")
    if not url or url.startswith("https://stub."):
        return None
    import httpx
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    path = os.path.join(RESULTS_DIR, f"export_src_{uuid.uuid4().hex}.jpg")
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


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


@router.get("/{product_id}/export")
def export_content(product_id: str, format: str = "feed", db: Session = Depends(get_db)):
    """화보를 인스타 포맷(feed 1080x1350 / reel·story 1080x1920)으로 리사이즈해 다운로드 (SCR-004, B-3)."""
    if format not in FORMATS:
        raise HTTPException(status_code=400, detail=f"지원 포맷: {list(FORMATS.keys())}")

    img = (
        db.query(GenerationJob)
        .filter(GenerationJob.product_id == product_id, GenerationJob.type == "image")
        .order_by(GenerationJob.created_at.desc())
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="화보가 없습니다")

    source = _local_source(img.result_refs or {})
    if not source:
        raise HTTPException(status_code=409, detail="스텁 화보라 내보낼 수 없습니다")

    data = export_bytes(source, format)
    w, h = FORMATS[format]
    filename = f"{product_id[:8]}_{format}_{w}x{h}.jpg"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="image/jpeg",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
