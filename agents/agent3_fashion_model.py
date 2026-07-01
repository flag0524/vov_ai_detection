# Agent 3: Higgsfield Soul ID 학습·이미지 생성 (토큰 없을 때는 스텁 반환)
import os
import uuid

HIGGSFIELD_TOKEN = os.getenv("HIGGSFIELD_API_KEY", "")


def create_soul_id(model_attrs: dict, reference_image_path: str) -> dict:
    """Soul Character를 학습하고 soul_reference_id를 반환한다.
    토큰 미설정 시 스텁 ID를 반환하고 stub=True 플래그를 표시한다."""
    if not HIGGSFIELD_TOKEN:
        stub_id = f"STUB_SOUL_{uuid.uuid4().hex[:8].upper()}"
        return {"soul_reference_id": stub_id, "stub": True, "reason": "HIGGSFIELD_API_KEY 미설정"}

    # TODO: 실제 Higgsfield MCP 호출
    # from mcp_client import call_higgsfield
    # result = call_higgsfield("higgsfield-soul-id", {...})
    raise NotImplementedError("Higgsfield MCP 호출 미구현 — 토큰 설정 후 구현")


def generate_image(prompt: str, soul_reference_id: str, product_image_path: str, model_id: str) -> dict:
    """Higgsfield로 패션 화보 이미지를 생성한다.
    토큰 미설정 시 스텁 URL을 반환한다."""
    if not HIGGSFIELD_TOKEN or soul_reference_id.startswith("STUB_"):
        stub_url = f"https://stub.jblanc.ai/images/{uuid.uuid4().hex}.jpg"
        return {"image_url": stub_url, "job_id": f"STUB_JOB_{uuid.uuid4().hex[:8]}", "stub": True}

    # TODO: 실제 Higgsfield MCP 호출
    raise NotImplementedError("Higgsfield MCP 호출 미구현 — 토큰 설정 후 구현")
