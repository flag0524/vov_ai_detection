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


def test_corrupt_image_rejected_with_400(client):
    """회귀 테스트: 손상 이미지는 업로드 시점에 400으로 거부.
    (브라우저 E2E에서 4바이트 더미 파일이 /pipeline/run을 500으로 죽이던 버그)"""
    resp = client.post(
        "/product/upload",
        files={"file": ("bad.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
    )
    assert resp.status_code == 400


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


# --- Phase 4: SNS 콘텐츠 (규칙 기반 템플릿, ADR-012) ---

def test_sns_template_contains_brand_hashtag():
    """tests.md Phase 4: 해시태그 #제이블랑 포함 + 관련 태그 5개 이상"""
    from agents.agent5_marketing import generate_sns_content
    result = generate_sns_content({"product_name": "테스트 원피스", "category": "원피스", "color": "블랙"})
    assert "#제이블랑" in result["hashtags"]
    assert len(result["hashtags"]) >= 5
    assert "테스트 원피스" in result["caption"]
    # tests.md Phase 4: 광고 카피 채널 길이 제한 (PRD: 20자 이내)
    assert 0 < len(result["ad_copy"]) <= 20


def test_upload_with_product_metadata(client):
    """ADR-012: 업로드 시 입력한 상품 정보가 저장되고 파이프라인 프롬프트에 반영"""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(30, 30, 60)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post(
        "/product/upload",
        files={"file": ("navy.png", buf, "image/png")},
        data={"name": "네이비 트위드 재킷", "category": "재킷", "color": "네이비", "style": "럭셔리"},
    )
    assert resp.status_code == 200
    product_id = resp.json()["product_id"]

    result = client.post("/pipeline/run", json={"product_id": product_id}).json()
    # 입력한 상품 정보가 생성 프롬프트에 반영됐는지 확인
    assert "네이비" in result["prompt"]
    assert "재킷" in result["prompt"]
    assert "네이비 트위드 재킷" in result["sns"]["caption"]


# --- SCREEN_DESIGN §2.6: 배경/씨 선택 (모델·상품 고정, 배경만 변경) ---

def test_resolve_background_precedence():
    """커스텀 > 프리셋 > 기본값(studio_white) 우선순위"""
    from agents.agent2_prompt_engineer import resolve_background, PRESET_SCENES
    # 커스텀 우선
    assert resolve_background("city_street", "  한강 산책로  ") == "한강 산책로"
    # 프리셋 매핑
    assert resolve_background("cafe", "") == PRESET_SCENES["cafe"]
    # 알 수 없는/빈 값은 기본값
    assert resolve_background(None, None) == PRESET_SCENES["studio_white"]
    assert resolve_background("no_such_preset", "") == PRESET_SCENES["studio_white"]


def test_pipeline_background_preset_injected_into_prompt(client):
    """프리셋 씨가 화보 프롬프트 Scene 절에 주입된다"""
    from agents.agent2_prompt_engineer import PRESET_SCENES
    product_id = _upload_product(client)
    result = client.post(
        "/pipeline/run",
        json={"product_id": product_id, "background": {"preset": "city_street"}},
    ).json()
    assert PRESET_SCENES["city_street"] in result["prompt"]


def test_pipeline_background_custom_overrides_preset(client):
    """커스텀 배경 텍스트가 프리셋보다 우선 주입된다"""
    product_id = _upload_product(client)
    result = client.post(
        "/pipeline/run",
        json={
            "product_id": product_id,
            "background": {"preset": "studio_white", "custom": "노을 지는 한강 산책로"},
        },
    ).json()
    assert "노을 지는 한강 산책로" in result["prompt"]


def test_pipeline_no_background_defaults_studio(client):
    """background 미지정 시 기본값(studio_white)으로 동작 — 하위 호환"""
    from agents.agent2_prompt_engineer import PRESET_SCENES
    product_id = _upload_product(client)
    result = client.post("/pipeline/run", json={"product_id": product_id}).json()
    assert PRESET_SCENES["studio_white"] in result["prompt"]


# --- SCREEN_DESIGN §2.5 #4·#5: 모델 고정 / 자연스러운 동작 ---

def test_pipeline_reuses_model_keeps_same_soul_id(client):
    """model_id 전달 시 같은 모델·Soul ID를 재사용한다 (모델 동일성 유지 #4)"""
    product_id = _upload_product(client)
    first = client.post("/pipeline/run", json={"product_id": product_id}).json()
    second = client.post(
        "/pipeline/run",
        json={"product_id": product_id, "model_id": first["model_id"]},
    ).json()
    assert second["model_id"] == first["model_id"]
    assert second["soul_reference_id"] == first["soul_reference_id"]


def test_pipeline_camera_motion_passthrough(client):
    """camera_motion이 응답에 반영된다 (자연스러운 동작 연출 #5)"""
    product_id = _upload_product(client)
    result = client.post(
        "/pipeline/run",
        json={"product_id": product_id, "camera_motion": "orbit"},
    ).json()
    assert result["camera_motion"] == "orbit"


def test_pipeline_camera_motion_defaults_dolly_in(client):
    """camera_motion 미지정 시 기본값 dolly_in"""
    product_id = _upload_product(client)
    result = client.post("/pipeline/run", json={"product_id": product_id}).json()
    assert result["camera_motion"] == "dolly_in"


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
