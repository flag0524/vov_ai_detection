# Agent 4: Higgsfield image-to-video로 릴스 영상을 생성 (자격증명 없으면 스텁 반환)
import uuid

from agents import higgsfield_client as hf

# Higgsfield 자체 DoP 모델 — 카메라 워킹 중심 image-to-video
VIDEO_MODEL = "higgsfield-ai/dop/preview"

# camera_motion 파라미터 → 영상 프롬프트 문구 매핑
CAMERA_MOTION_PROMPTS = {
    "dolly_in": "slow cinematic dolly-in toward the model",
    "dolly_out": "slow cinematic dolly-out from the model",
    "orbit": "smooth orbit around the model",
    "pan": "gentle horizontal pan across the scene",
    "static": "static camera, subtle natural motion only",
}


def generate_video(image_url: str, duration_sec: int = 10, aspect_ratio: str = "9:16", camera_motion: str = "dolly_in") -> dict:
    """이미지 URL을 입력받아 패션 릴스 영상을 생성한다.
    자격증명 미설정 또는 스텁 이미지 입력 시 스텁 URL을 반환한다."""
    if duration_sec < 5 or duration_sec > 15:
        raise ValueError("duration_sec은 5~15초 범위여야 합니다.")

    def _stub(reason: str = "") -> dict:
        result = {
            "video_url": f"https://stub.jblanc.ai/videos/{uuid.uuid4().hex}.mp4",
            "job_id": f"STUB_VID_{uuid.uuid4().hex[:8]}",
            "duration_sec": duration_sec,
            "aspect_ratio": aspect_ratio,
            "stub": True,
        }
        if reason:
            result["reason"] = reason
        return result

    # 스텁 이미지는 Higgsfield가 다운로드할 수 없으므로 실호출 불가
    if not hf.credentials_available() or image_url.startswith("https://stub."):
        return _stub()

    motion_prompt = CAMERA_MOTION_PROMPTS.get(camera_motion, CAMERA_MOTION_PROMPTS["dolly_in"])
    try:
        result = hf.generate(
            VIDEO_MODEL,
            {
                "image_url": image_url,
                "prompt": f"luxury fashion editorial reel, {motion_prompt}, natural elegant movement",
                "duration": duration_sec,
            },
            timeout_sec=600,  # 영상은 이미지보다 오래 걸림
        )
        video = result.get("video") or {}
        video_url = video.get("url") if isinstance(video, dict) else video
        if not video_url:
            raise hf.HiggsfieldError(f"응답에 video 없음: {result}")
        return {
            "video_url": video_url,
            "job_id": result.get("request_id", ""),
            "duration_sec": duration_sec,
            "aspect_ratio": aspect_ratio,
            "stub": False,
        }
    except hf.HiggsfieldError as e:
        # 크레딧 부족 등 API 실패 시 파이프라인을 죽이지 않고 스텁으로 강등
        return _stub(reason=str(e))
