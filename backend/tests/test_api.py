# tests.md의 Phase 0/1/2/4/5 스텁 모드 검증 기준을 코드로 고정한 API 테스트
import io


def _upload_product(client):
    """유효한 PNG를 업로드하고 product_id를 반환하는 헬퍼."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(120, 80, 200)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post(
        "/product/upload",
        files={"file": ("test.png", buf, "image/png")},
    )
    assert resp.status_code == 200
    return resp.json()["product_id"]


# --- Phase 0: 기반 셋업 ---

def test_health(client):
    """tests.md Phase 0: GET /health → 200, {"status":"ok"}"""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_orm_tables_exist():
    """tests.md Phase 0: AIModel, Product, GenerationJob, Content 테이블 존재"""
    from app.models.base import Base
    tables = set(Base.metadata.tables.keys())
    assert {"ai_models", "products", "generation_jobs", "contents"} <= tables


def test_product_upload_and_get(client):
    """tests.md Phase 0: 파일 업로드 → product_id 반환 및 조회 가능"""
    product_id = _upload_product(client)
    resp = client.get(f"/product/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["product_id"] == product_id


# --- Phase 1: 모델 생성 (스텁 모드) ---

def test_model_create_stores_soul_reference_id(client):
    """tests.md Phase 1: POST /ai/model/create → soul_reference_id 저장.
    HIGGSFIELD_API_KEY 미설정 시 스텁 ID + stub=True."""
    resp = client.post("/ai/model/create", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["soul_reference_id"].startswith("STUB_SOUL_")
    assert body["stub"] is True
    assert body["model_id"]


# --- Phase 2/5: E2E 파이프라인 (스텁 모드) ---

def test_pipeline_run_full_e2e_stub(client):
    """tests.md Phase 5: 상품 1건 업로드 → 화보·릴스·카피 모두 산출.
    스텁 모드에서는 image/video가 스텁 URL, SSIM은 실계산."""
    product_id = _upload_product(client)
    resp = client.post("/pipeline/run", json={"product_id": product_id})
    assert resp.status_code == 200
    body = resp.json()

    # 산출물 3종
    assert body["image_url"]
    assert body["video_url"]
    assert body["sns"]["caption"]

    # 품질 게이트 (동일 이미지 비교라 통과해야 함)
    assert body["quality"]["overall_pass"] is True
    assert body["quality"]["ssim_score"] >= 0.80

    # Phase 6: 재생성 시도 횟수·처리 시간 기록
    assert body["regeneration_attempts"] >= 1
    assert body["processing_time_sec"] >= 0

    # 스텁 플래그 명시 (실생성물로 오인 방지)
    assert body["stubs"]["image"] is True
    assert body["stubs"]["video"] is True


def test_pipeline_run_404_for_missing_product(client):
    resp = client.post("/pipeline/run", json={"product_id": "no-such-id"})
    assert resp.status_code == 404


# --- Phase 4: SNS 콘텐츠 (스텁 모드) ---

def test_sns_stub_contains_brand_hashtag():
    """tests.md Phase 4: 해시태그에 #제이블랑 포함 (스텁 fallback 기준)"""
    from agents.agent5_marketing import generate_sns_content
    result = generate_sns_content({"product_name": "테스트 원피스"})
    assert result.get("stub") is True
    assert "#제이블랑" in result["hashtags"]
    assert result["caption"]


# --- Phase 3: 영상 생성 파라미터 검증 ---

def test_video_duration_range_enforced():
    """tests.md Phase 3: 영상은 5~15초 — 범위 밖 duration은 거부"""
    import pytest
    from agents.agent4_video_creator import generate_video
    with pytest.raises(ValueError):
        generate_video(image_url="https://stub.jblanc.ai/x.jpg", duration_sec=3)
    with pytest.raises(ValueError):
        generate_video(image_url="https://stub.jblanc.ai/x.jpg", duration_sec=20)
    ok = generate_video(image_url="https://stub.jblanc.ai/x.jpg", duration_sec=10)
    assert ok["stub"] is True
    assert ok["aspect_ratio"] == "9:16"
