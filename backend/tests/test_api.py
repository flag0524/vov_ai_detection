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

    # ADR-013: 파이프라인은 화보 + SNS 카피까지. 영상은 화보 확인 후 별도 트리거
    assert body["image_url"]
    assert body["video_url"] is None
    assert body["sns"]["caption"]

    # 품질 게이트 (동일 이미지 비교라 통과해야 함)
    assert body["quality"]["overall_pass"] is True
    assert body["quality"]["ssim_score"] >= 0.80

    # Phase 6: 재생성 시도 횟수·처리 시간 기록
    assert body["regeneration_attempts"] >= 1
    assert body["processing_time_sec"] >= 0

    # 스텁 플래그 명시 (실생성물로 오인 방지)
    assert body["stubs"]["image"] is True


def test_reel_generated_only_after_photoshoot(client):
    """ADR-013: 릴스는 화보 확인 후 POST /pipeline/video로 생성한다"""
    product_id = _upload_product(client)
    # 화보 없이 영상 요청 → 404
    assert client.post("/pipeline/video", json={"product_id": product_id}).status_code == 404
    # 화보 생성 후에는 릴스 생성 가능
    client.post("/pipeline/run", json={"product_id": product_id})
    resp = client.post("/pipeline/video", json={"product_id": product_id, "camera_motion": "orbit"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["video_url"]
    assert body["camera_motion"] == "orbit"
    # 라이브러리에도 영상이 붙는다
    items = client.get("/contents").json()["items"]
    assert items[0]["video_url"] == body["video_url"]


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


def test_summer_theme_presets_exist():
    """여름·미니멀·모던 테마 프리셋 (도심 테라스/지중해/풀사이드/스톤 코트야드)"""
    from agents.agent2_prompt_engineer import PRESET_SCENES
    for key in ("luxury_terrace", "mediterranean", "resort_poolside", "stone_courtyard"):
        assert key in PRESET_SCENES
        assert "summer" in PRESET_SCENES[key]


def test_prompt_locks_korean_proportions_and_reference_garment(client):
    """프롬프트가 참조 상품·체형·보행·실사 품질을 모두 지시한다 (사용자 지정 템플릿)"""
    product_id = _upload_product(client)
    result = client.post("/pipeline/run", json={"product_id": product_id}).json()
    p = result["prompt"]
    # 상품 보존 (flux-2 image_urls, ADR-015)
    assert "reference image" in p
    # 비율 왜곡 방지 — 전속 모델 키 169~170cm, 7~7.5등신 (9등신 과장 금지)
    assert "Korean adult female body proportions" in p
    assert "height 169-170cm" in p
    assert "7 to 7.5 heads tall" in p
    assert "NOT a 9-head figure" in p
    # 자연스러운 보행 (발 미끄러짐 방지) + 신발 착용 (맨발 결함 대응)
    assert "no sliding effect" in p
    assert "never barefoot" in p
    # 'AI스러움' 제거 — 실사 화보 품질
    assert "35mm lens" in p
    assert "NOT CGI looking" in p


def test_negative_prompt_blocks_ai_artifacts_and_distortion():
    """네거티브가 AI 아티팩트·만화체·다리 늘어남·보행 왜곡을 차단한다"""
    from agents.agent2_prompt_engineer import generate_photoshoot_prompt
    neg = generate_photoshoot_prompt({}, {})["negative_prompt"]
    for term in ("AI artifacts", "cartoon", "anime", "unnaturally long legs",
                 "stretched body", "unnatural walking", "sliding feet", "messy background"):
        assert term in neg


def test_negative_prompt_blocks_garment_alteration():
    """의상 변형 차단 — 파일럿에서 캡소매가 긴소매로 바뀐 실측 결함 대응"""
    from agents.agent2_prompt_engineer import generate_photoshoot_prompt
    neg = generate_photoshoot_prompt({}, {})["negative_prompt"]
    for term in ("changed sleeve length", "altered garment silhouette", "added sleeves",
                 "changed neckline", "changed hem length", "different garment"):
        assert term in neg
    # 맨발 결함(파일럿 4장 중 2장) 대응
    for term in ("barefoot", "bare feet", "missing shoes"):
        assert term in neg


def test_negative_prompt_is_actually_sent_to_higgsfield(monkeypatch):
    """회귀: negative_prompt가 flux-2 페이로드에 실제로 실려야 한다.
    (예전엔 agent2가 만들기만 하고 agent3가 안 보내서 네거티브가 전부 무효였음)"""
    from agents import agent3_fashion_model as a3
    from agents import higgsfield_client as hf

    sent = {}

    def fake_generate(model_id, payload, **kw):
        sent["model_id"] = model_id
        sent["payload"] = payload
        return {"images": [{"url": "https://example.com/x.png"}], "request_id": "r1"}

    monkeypatch.setattr(hf, "credentials_available", lambda: True)
    monkeypatch.setattr(hf, "generate", fake_generate)

    r = a3.generate_image("a prompt", "", "", "m1", negative_prompt="changed sleeve length")
    assert r["stub"] is False
    assert sent["model_id"] == "flux-2"
    assert sent["payload"]["negative_prompt"] == "changed sleeve length"


def test_model_registry_has_three_models_with_multi_angle_refs():
    """전속 모델 3명, 각각 다각도 참조 3장(정면·45도·측면)"""
    from agents import model_registry
    models = model_registry.list_models()
    assert {m["key"] for m in models} == {"elegant", "chic", "natural"}
    for m in models:
        assert m["thumbnail_url"].startswith("https://")
        assert len(model_registry.reference_urls(m["key"])) == 3
    # 알 수 없는 키는 기본 모델로 폴백
    assert model_registry.get_model("nope")["key"] == model_registry.default_key()


def test_selected_model_references_are_sent(monkeypatch):
    """선택한 모델의 다각도 참조가 image_urls에 상품 다음으로 모두 실려야 한다.
    (LoRA 대신 flux-2 다각도 참조로 얼굴 고정 — A/B 실측)"""
    from agents import agent3_fashion_model as a3
    from agents import higgsfield_client as hf, model_registry

    sent = {}
    monkeypatch.setattr(hf, "credentials_available", lambda: True)
    monkeypatch.setattr(hf, "generate", lambda m, p, **k: sent.update(payload=p) or
                        {"images": [{"url": "https://x/y.png"}], "request_id": "r"})
    monkeypatch.setattr(hf, "upload_image", lambda path, **k: "https://x/product.jpg")
    monkeypatch.setattr(a3.os.path, "exists", lambda p: True)

    a3.generate_image("p", "", "/tmp/product.jpg", "m1", model_key="chic")
    urls = sent["payload"]["image_urls"]
    assert urls[0] == "https://x/product.jpg"                    # 상품이 먼저
    assert urls[1:] == model_registry.reference_urls("chic")     # 선택 모델 다각도 3장


def test_models_endpoint_lists_three(client):
    """GET /ai/models — 전속 모델 3명 + 기본 모델"""
    body = client.get("/ai/models").json()
    assert len(body["models"]) == 3
    assert body["default"] == "elegant"
    assert all(m["thumbnail_url"] for m in body["models"])


def test_pipeline_uses_selected_model(client):
    """model_key로 전속 모델을 선택하면 응답에 반영된다"""
    product_id = _upload_product(client)
    r = client.post("/pipeline/run", json={"product_id": product_id, "model_key": "natural"}).json()
    assert r["model_key"] == "natural"
    assert r["model_name"] == "깨끗·내추럴"


def test_identity_lock_only_when_model_reference_present():
    """전속 모델 참조가 있을 때만 identity-lock 절을 붙인다 (모델 참조의 흰 티셔츠 혼입 방지)"""
    from agents.agent3_fashion_model import apply_identity_lock
    base = "A fashion photo."
    # 상품 참조만 있으면 그대로
    assert apply_identity_lock(base, has_model_reference=False) == base
    # 모델 참조가 있으면 얼굴만 가져오고 의상은 상품 참조에서 가져오도록 명시
    locked = apply_identity_lock(base, has_model_reference=True)
    assert "Identity lock" in locked
    assert "ONLY the face and identity" in locked
    assert "Do NOT copy the plain white t-shirt" in locked


def test_brand_name_defaults_to_jblanc():
    """브랜드명은 상수로 분리 — ADR-014 기준 기본값 JBLANC (VOV는 벤치마크, 주입 금지)"""
    from agents.agent2_prompt_engineer import BRAND_NAME, generate_photoshoot_prompt
    assert BRAND_NAME == "JBLANC"
    assert "JBLANC" in generate_photoshoot_prompt({}, {})["prompt"]


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


# --- SCREEN_DESIGN §2.5: AI 이미지 분석 (색상 자동 추출, ADR-012 준수) ---

def test_extract_palette_solid_color():
    """단색 이미지는 그 색을 지배색으로 추출한다 (외부 API 없음, 결정적)"""
    from PIL import Image
    from app.services.palette import extract_palette
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(120, 80, 200)).save(buf, format="PNG")
    palette = extract_palette(buf.getvalue(), n=5)
    assert palette
    assert palette[0]["hex"] == "#7850C8"
    assert palette[0]["ratio"] == 1.0


def test_analyze_palette_endpoint(client):
    """POST /product/analyze-palette → 색상 팔레트 반환"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(20, 200, 90)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post(
        "/product/analyze-palette",
        files={"file": ("p.png", buf, "image/png")},
    )
    assert resp.status_code == 200
    palette = resp.json()["palette"]
    assert palette and palette[0]["hex"] == "#14C85A"


def test_analyze_palette_rejects_corrupt_image(client):
    """손상 이미지는 400"""
    resp = client.post(
        "/product/analyze-palette",
        files={"file": ("bad.jpg", io.BytesIO(b"\xff\xd8\xff\xe0"), "image/jpeg")},
    )
    assert resp.status_code == 400


def test_upload_accepts_silhouette(client):
    """업로드가 silhouette를 받아 저장하고 프롬프트에 반영한다 (담당자 입력)"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(40, 40, 40)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post(
        "/product/upload",
        files={"file": ("s.png", buf, "image/png")},
        data={"name": "테스트", "silhouette": "A라인 맥시"},
    )
    assert resp.status_code == 200
    product_id = resp.json()["product_id"]
    result = client.post("/pipeline/run", json={"product_id": product_id}).json()
    assert "A라인 맥시" in result["prompt"]


# --- SCREEN_DESIGN §2.5: 품번 자동채번 (카테고리 코드 기반) ---

def _upload_with_category(client, category):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(90, 90, 90)).save(buf, format="PNG")
    buf.seek(0)
    return client.post(
        "/product/upload",
        files={"file": ("c.png", buf, "image/png")},
        data={"category": category},
    ).json()

def test_sku_category_code_and_sequence(client):
    """상의/하의/원피스/아우터 코드 매핑 + 카테고리별 순번 증가"""
    assert _upload_with_category(client, "원피스")["sku"] == "JBL-OPS-001"
    assert _upload_with_category(client, "원피스")["sku"] == "JBL-OPS-002"
    assert _upload_with_category(client, "상의")["sku"] == "JBL-TOP-001"
    assert _upload_with_category(client, "하의")["sku"] == "JBL-BTM-001"
    assert _upload_with_category(client, "아우터")["sku"] == "JBL-OUT-001"

def test_sku_unknown_category_is_gen(client):
    """미지정/기타 카테고리는 GEN 코드"""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (16, 16), color=(10, 10, 10)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post("/product/upload", files={"file": ("g.png", buf, "image/png")})
    assert resp.json()["sku"] == "JBL-GEN-001"


# --- SCREEN_DESIGN §5: 콘텐츠 라이브러리 (GET /contents) ---

def test_contents_lists_generated_products(client):
    """생성 파이프라인을 거친 상품이 /contents 목록에 화보/릴스와 함께 노출된다"""
    product_id = _upload_product(client)
    client.post("/pipeline/run", json={"product_id": product_id})
    resp = client.get("/contents")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    it = items[0]
    assert it["product_id"] == product_id
    assert it["image_url"]
    assert it["caption"]
    # ADR-013: 영상은 화보 확인 후 생성하므로 이 시점엔 없다
    assert it["video_url"] is None

def test_contents_empty_when_no_generation(client):
    """업로드만 하고 생성 안 한 상품은 라이브러리에 안 나온다"""
    _upload_product(client)
    resp = client.get("/contents")
    assert resp.json()["items"] == []

def test_contents_filters_by_category(client):
    """category 쿼리로 카테고리별 필터링"""
    from PIL import Image
    def up(cat):
        buf = io.BytesIO()
        Image.new("RGB", (16, 16), color=(70, 70, 70)).save(buf, format="PNG")
        buf.seek(0)
        pid = client.post("/product/upload", files={"file": ("c.png", buf, "image/png")},
                          data={"category": cat}).json()["product_id"]
        client.post("/pipeline/run", json={"product_id": pid})
    up("상의")
    up("하의")
    resp = client.get("/contents", params={"category": "상의"})
    items = resp.json()["items"]
    assert len(items) == 1 and items[0]["category"] == "상의"


# --- SCR-002 검수·재생성 (ADR-013) ---

def _generated_job(client):
    """화보를 하나 생성하고 검수 job을 돌려주는 헬퍼."""
    product_id = _upload_product(client)
    client.post("/pipeline/run", json={"product_id": product_id})
    items = client.get("/review/jobs").json()["items"]
    assert items
    return items[0]


def test_review_list_shows_original_and_generated(client):
    """검수 목록에 원본 URL·생성 화보·SSIM·상태가 함께 나온다 (비교 뷰용)"""
    it = _generated_job(client)
    assert it["original_url"].startswith("/storage/uploads/")
    assert it["image_url"]
    assert it["ssim"] is not None
    assert it["qa_status"] in ("approved", "manual_review")
    assert it["attempts"] == 1


def test_review_list_survives_legacy_string_background(client):
    """회귀: 구 스키마 job은 params.background가 문자열이다.
    딕셔너리로 가정하면 검수 목록이 500으로 죽는다 (실 DB에서 발생)."""
    from app.api.review import _scene_of
    assert _scene_of({"background": "Seoul luxury boutique"}) == "Seoul luxury boutique"
    assert _scene_of({"background": {"scene": "city street"}}) == "city street"
    assert _scene_of({}) is None
    assert _scene_of(None) is None


def test_review_approve_transitions_job_and_content(client):
    """승인 시 job.qa_status와 Content.status가 함께 approved로 전이"""
    it = _generated_job(client)
    r = client.patch(f"/review/jobs/{it['job_id']}", json={"action": "approve"}).json()
    assert r["qa_status"] == "approved"
    assert r["content_status"] == "approved"
    assert client.get("/review/jobs", params={"status": "approved"}).json()["items"]


def test_review_discard_marks_job_failed(client):
    """폐기 시 job은 failed, Content는 discarded — 배포 대상에서 제외"""
    it = _generated_job(client)
    r = client.patch(f"/review/jobs/{it['job_id']}", json={"action": "discard"}).json()
    assert r["qa_status"] == "discarded"
    assert r["content_status"] == "discarded"


def test_review_rejects_unknown_action(client):
    it = _generated_job(client)
    assert client.patch(f"/review/jobs/{it['job_id']}", json={"action": "nope"}).status_code == 400


def test_review_regenerate_keeps_history_and_uses_edited_prompt(client):
    """재생성: 프롬프트 수정 반영 + 직전 결과를 이력으로 보존 + 회차 증가"""
    it = _generated_job(client)
    before = it["image_url"]
    r = client.post(f"/review/jobs/{it['job_id']}/regenerate",
                    json={"prompt": "수정된 프롬프트"}).json()
    assert r["attempts"] == 2
    assert r["image_url"] != before

    after = client.get("/review/jobs").json()["items"][0]
    assert after["prompt"] == "수정된 프롬프트"      # 수정된 프롬프트가 저장됨
    assert after["history"][0]["image_url"] == before  # 직전 결과가 이력에 남음


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
