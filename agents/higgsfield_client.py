# Higgsfield Platform API 공용 REST 클라이언트 (submit → poll 패턴)
import os
import time

import httpx

BASE_URL = "https://platform.higgsfield.ai"

API_KEY = os.getenv("HIGGSFIELD_API_KEY", "")
API_SECRET = os.getenv("HIGGSFIELD_API_SECRET", "")


class HiggsfieldError(Exception):
    """Higgsfield API 호출 실패 (인증·크레딧·생성 실패 포함)."""


def credentials_available() -> bool:
    """실호출에 필요한 key+secret 쌍이 모두 설정됐는지 여부."""
    return bool(API_KEY and API_SECRET)


def _auth_header() -> dict:
    return {"Authorization": f"Key {API_KEY}:{API_SECRET}"}


def submit(model_id: str, payload: dict) -> dict:
    """생성 작업을 제출하고 request_id/status_url을 반환한다."""
    resp = httpx.post(
        f"{BASE_URL}/{model_id}",
        headers={**_auth_header(), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise HiggsfieldError(f"submit 실패 ({resp.status_code}): {resp.text}")
    return resp.json()


def wait(request_id: str, timeout_sec: int = 300, interval_sec: float = 3.0) -> dict:
    """request_id의 상태를 completed/failed까지 폴링하고 최종 응답을 반환한다."""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        resp = httpx.get(
            f"{BASE_URL}/requests/{request_id}/status",
            headers=_auth_header(),
            timeout=30,
        )
        if resp.status_code >= 400:
            raise HiggsfieldError(f"status 조회 실패 ({resp.status_code}): {resp.text}")
        body = resp.json()
        status = body.get("status")
        if status == "completed":
            return body
        if status in ("failed", "canceled"):
            raise HiggsfieldError(f"생성 실패 (status={status}): {body}")
        time.sleep(interval_sec)
    raise HiggsfieldError(f"생성 타임아웃 ({timeout_sec}s, request_id={request_id})")


def generate(model_id: str, payload: dict, timeout_sec: int = 300) -> dict:
    """submit + wait 헬퍼. 완료된 최종 응답(dict)을 반환한다."""
    submitted = submit(model_id, payload)
    request_id = submitted.get("request_id")
    if not request_id:
        raise HiggsfieldError(f"request_id 없음: {submitted}")
    return wait(request_id, timeout_sec=timeout_sec)
