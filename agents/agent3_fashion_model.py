# Agent 3: Higgsfield Soul 모델로 패션 화보 이미지 생성 (자격증명 없으면 스텁 반환)
import uuid

from agents import higgsfield_client as hf

SOUL_IMAGE_MODEL = "higgsfield-ai/soul/standard"


def create_soul_id(model_attrs: dict, reference_image_path: str) -> dict:
    """Soul Character를 학습하고 soul_reference_id를 반환한다.

    참고: Higgsfield Platform API 공개 문서에는 Soul Character 학습(soul-id)
    엔드포인트가 아직 없어 (text2image `soul/standard`만 공개), 학습은
    스텁 ID로 대체하고 이미지 생성은 프롬프트 고정 토큰으로 일관성을 유지한다.
    학습 API 공개 시 이 함수만 교체하면 된다."""
    stub_id = f"STUB_SOUL_{uuid.uuid4().hex[:8].upper()}"
    reason = (
        "Soul 학습 API 미공개 — 프롬프트 고정 토큰으로 대체"
        if hf.credentials_available()
        else "HIGGSFIELD_API_KEY/SECRET 미설정"
    )
    return {"soul_reference_id": stub_id, "stub": True, "reason": reason}


def generate_image(prompt: str, soul_reference_id: str, product_image_path: str, model_id: str) -> dict:
    """Higgsfield Soul 모델로 패션 화보 이미지를 생성한다.
    자격증명 미설정 시 스텁 URL을 반환한다."""
    if not hf.credentials_available():
        stub_url = f"https://stub.jblanc.ai/images/{uuid.uuid4().hex}.jpg"
        return {"image_url": stub_url, "job_id": f"STUB_JOB_{uuid.uuid4().hex[:8]}", "stub": True}

    try:
        result = hf.generate(
            SOUL_IMAGE_MODEL,
            {
                "prompt": prompt,
                "aspect_ratio": "3:4",
                "resolution": "720p",
            },
        )
        images = result.get("images") or []
        if not images:
            raise hf.HiggsfieldError(f"응답에 images 없음: {result}")
        return {
            "image_url": images[0].get("url"),
            "job_id": result.get("request_id", ""),
            "stub": False,
        }
    except hf.HiggsfieldError as e:
        # 크레딧 부족 등 API 실패 시 파이프라인을 죽이지 않고 스텁으로 강등
        stub_url = f"https://stub.jblanc.ai/images/{uuid.uuid4().hex}.jpg"
        return {
            "image_url": stub_url,
            "job_id": f"STUB_JOB_{uuid.uuid4().hex[:8]}",
            "stub": True,
            "reason": str(e),
        }
