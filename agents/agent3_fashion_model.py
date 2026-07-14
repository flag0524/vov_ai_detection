# Agent 3: Higgsfield로 패션 화보 이미지 생성 (상품 보존 = flux-2 image_urls 참조, 자격증명 없으면 스텁)
import os
import uuid

from agents import higgsfield_client as hf

SOUL_IMAGE_MODEL = "higgsfield-ai/soul/standard"
# 상품 원본 보존: flux-2에 상품 이미지를 image_urls 참조로 주입 (soul/standard 텍스트 생성은 상품 무시)
REFERENCE_IMAGE_MODEL = "flux-2"
from agents import model_registry


def model_reference_urls(model_key: str = None) -> list[str]:
    """선택된 전속 모델의 다각도 참조 URL(정면·45도·측면).
    다각도를 넣으면 얼굴 고정 정확도가 올라간다 (A/B 실측, 상품 참조 희석 없음)."""
    return model_registry.reference_urls(model_key)


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


def apply_identity_lock(prompt: str, has_model_reference: bool) -> str:
    """참조가 2장(상품 + 전속 모델)일 때, 어느 참조에서 무엇을 가져올지 명시한다.
    이 절이 없으면 모델 참조의 흰 티셔츠·스튜디오 배경이 결과물에 섞인다 (실측 확인)."""
    if not has_model_reference:
        return prompt
    return (
        f"{prompt} Identity lock: the model's face, hair and identity must exactly match "
        f"the person in the model reference image (the plain studio portrait). "
        f"Take ONLY the face and identity from that reference — the outfit must come from "
        f"the product reference image. Do NOT copy the plain white t-shirt or the studio "
        f"background from the model reference."
    )


def generate_image(prompt: str, soul_reference_id: str, product_image_path: str, model_id: str,
                   negative_prompt: str = "", model_key: str = None) -> dict:
    """flux-2 참조 생성으로 패션 화보를 만든다. 상품 이미지를 image_urls 참조로 주입해
    상품 원본(디자인·색상·패턴)을 보존한다. 자격증명 미설정/실패 시 스텁으로 강등한다."""
    def _stub(reason: str = "") -> dict:
        out = {"image_url": f"https://stub.jblanc.ai/images/{uuid.uuid4().hex}.jpg",
               "job_id": f"STUB_JOB_{uuid.uuid4().hex[:8]}", "stub": True}
        if reason:
            out["reason"] = reason
        return out

    if not hf.credentials_available():
        return _stub()

    try:
        # 상품 이미지를 Higgsfield에 업로드해 참조 URL 확보 (상품 보존의 핵심)
        image_urls = []
        if product_image_path and os.path.exists(product_image_path):
            image_urls.append(hf.upload_image(product_image_path))
        model_refs = model_reference_urls(model_key)  # 선택 모델의 정면·45도·측면
        image_urls.extend(model_refs)

        prompt = apply_identity_lock(prompt, has_model_reference=bool(model_refs))

        payload = {"prompt": prompt, "aspect_ratio": "9:16", "resolution": "2k"}
        if negative_prompt:
            # 네거티브를 안 보내면 의상 변형·비율 왜곡 차단이 전혀 걸리지 않는다
            payload["negative_prompt"] = negative_prompt
        if image_urls:
            payload["image_urls"] = image_urls  # flux-2 참조 이미지 (상품 → 모델 순)

        result = hf.generate(REFERENCE_IMAGE_MODEL, payload)
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
        return _stub(reason=str(e))
