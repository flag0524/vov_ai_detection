# 상품 업로드 및 조회 라우터
import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.models.base import get_db
from app.models.entities import Product

router = APIRouter(prefix="/product", tags=["product"])

STORAGE_DIR = os.getenv("STORAGE_LOCAL_DIR", "../storage")


@router.post("/upload")
async def upload_product(file: UploadFile = File(...), db: Session = Depends(get_db)):
    product_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "image.jpg")[1]
    save_path = os.path.join(STORAGE_DIR, "uploads", f"{product_id}{ext}")
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    async with aiofiles.open(save_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    product = Product(product_id=product_id, name=file.filename, image_ref=save_path)
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
