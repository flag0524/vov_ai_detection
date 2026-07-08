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
from app.services.palette import extract_palette

router = APIRouter(prefix="/product", tags=["product"])

STORAGE_DIR = os.getenv("STORAGE_LOCAL_DIR", "../storage")

# 카테고리 → 품번 코드 (상의/하의 구분 포함). 프론트 카테고리 칩과 일치.
CATEGORY_CODES = [("상의", "TOP"), ("하의", "BTM"), ("원피스", "OPS"), ("아우터", "OUT")]


def _category_code(category: str | None) -> str:
    for keyword, code in CATEGORY_CODES:
        if category and keyword in category:
            return code
    return "GEN"


def _generate_sku(db: Session, category: str | None) -> str:
    """JBL-{코드}-{순번} 형식 품번을 카테고리별 상품 수로 생성한다 (표시용, 비영속).
    영속 식별이 필요해지면(SCR-004 라이브러리) Product.sku 컬럼으로 승격."""
    code = _category_code(category)
    q = db.query(Product)
    if category:
        q = q.filter(Product.category == category)
    return f"JBL-{code}-{q.count() + 1:03d}"


@router.post("/upload")
async def upload_product(
    file: UploadFile = File(...),
    # 상품 정보 직접 입력 (ADR-012 — Vision 자동 분석 대신 담당자가 입력)
    name: str = Form(None),
    category: str = Form(None),
    color: str = Form(None),
    material: str = Form(None),
    silhouette: str = Form(None),
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

    sku = _generate_sku(db, category)

    product = Product(
        product_id=product_id,
        name=name or file.filename,
        category=category,
        color=color,
        material=material,
        silhouette=silhouette,
        style=style,
        target_customer=target_customer,
        image_ref=save_path,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    return {"product_id": product.product_id, "sku": sku, "image_ref": product.image_ref}


@router.post("/analyze-palette")
async def analyze_palette(file: UploadFile = File(...)):
    """업로드 이미지에서 지배 색상 팔레트를 추출한다 (자동, 외부 API 없음 — ADR-012 준수).
    소재·핏·스타일 등 나머지 속성은 담당자가 직접 입력한다 (Vision 자동분석 폐기)."""
    content = await file.read()
    try:
        palette = extract_palette(content, n=5)
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise HTTPException(status_code=400, detail="유효한 이미지 파일이 아닙니다")
    return {"palette": palette}


@router.get("/{product_id}")
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.product_id == product_id).first()
    if not product:
        return {"error": "not found"}
    return {"product_id": product.product_id, "name": product.name, "image_ref": product.image_ref}
