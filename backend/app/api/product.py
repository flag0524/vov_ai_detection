# 상품 업로드 및 조회 라우터
import io
import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product

router = APIRouter(prefix="/product", tags=["product"])

STORAGE_DIR = os.getenv("STORAGE_LOCAL_DIR", "../storage")


@router.post("/upload")
async def upload_product(
    file: UploadFile = File(...),
    # 상품 정보 직접 입력 (ADR-012 — Vision 자동 분석 대신 담당자가 입력)
    name: str = Form(None),
    category: str = Form(None),
    color: str = Form(None),
    material: str = Form(None),
    style: str = Form(None),
    target_customer: str = Form(None),
    db: Session = Depends(get_db),
):
    content = await file.read()

    # 손상/비이미지 파일은 저장 전에 거부 (파이프라인 SSIM 단계에서 500으로 죽는 것 방지)
    try:
        Image.open(io.BytesIO(content)).verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(status_code=400, detail="유효한 이미지 파일이 아닙니다")

    product_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "image.jpg")[1]
    save_path = os.path.join(STORAGE_DIR, "uploads", f"{product_id}{ext}")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    async with aiofiles.open(save_path, "wb") as f:
        await f.write(content)

    product = Product(
        product_id=product_id,
        name=name or file.filename,
        category=category,
        color=color,
        material=material,
        style=style,
        target_customer=target_customer,
        image_ref=save_path,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return {"product_id": product.product_id, "image_ref": product.image_ref}


@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        return {"error": "not found"}
    return {"product_id": product.product_id, "name": product.name, "image_ref": product.image_ref}
