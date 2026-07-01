# Agent 4: Higgsfield image-to-video로 릴스 영상을 생성 (토큰 없을 때는 스텁 반환)
import os
import uuid

HIGGSFIELD_TOKEN = os.getenv("HIGGSFIELD_API_KEY", "")


def generate_video(image_url: str, duration_sec: int = 10, aspect_ratio: str = "9:16", camera_motion: str = "dolly_in") -> dict:
    """이미지 URL을 입력받아 패션 릴스 영상을 생성한다.
    토큰 미설정 시 스텁 URL을 반환한다."""
    if duration_sec < 5 or duration_sec > 15:
        raise ValueError("duration_sec은 5~15초 범위여야 합니다.")

    if not HIGGSFIELD_TOKEN or image_url.startswith("https://stub."):
        stub_url = f"https://stub.jblanc.ai/videos/{uuid.uuid4().hex}.mp4"
        return {
            "video_url": stub_url,
            "job_id": f"STUB_VID_{uuid.uuid4().hex[:8]}",
            "duration_sec": duration_sec,
            "aspect_ratio": aspect_ratio,
            "stub": True,
        }

    # TODO: 실제 Higgsfield MCP 호출 (image-to-video)
    raise NotImplementedError("Higgsfield MCP 호출 미구현 — 토큰 설정 후 구현")
