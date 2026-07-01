# SNS 콘텐츠 생성 API 라우터
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Content, Product

router = APIRouter(prefix="/sns", tags=["sns"])


class ContentCreateRequest(BaseModel):
    product_id: str
    channel: str = "instagram"


@router.post("/content/create")
def create_content(req: ContentCreateRequest, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == req.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="product not found")

    from agents.agent1_product_analyzer import analyze_product_image
    from agents.agent5_marketing import generate_sns_content

    product_meta = analyze_product_image(product.image_ref) if os.path.exists(product.image_ref or "") else {
        "product_name": product.name,
        "category": "패션",
    }

    sns_result = generate_sns_content(product_meta, channel=req.channel)

    content = Content(
        content_id=str(uuid.uuid4()),
        source_ref=product.product_id,
        caption=sns_result.get("caption", ""),
        hashtags=sns_result.get("hashtags", []),
        ad_copy=sns_result.get("ad_copy", ""),
        channel=req.channel,
        status="draft",
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    return {
        "content_id": content.content_id,
        "caption": content.caption,
        "hashtags": content.hashtags,
        "ad_copy": content.ad_copy,
        "channel": content.channel,
    }
