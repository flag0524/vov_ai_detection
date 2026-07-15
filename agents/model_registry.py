# 전속 모델 레지스트리 — 모델 3명의 다각도 참조 URL(정면·45도·측면)을 로드한다 (ADR-015)
import json
import os
from functools import lru_cache

_REGISTRY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "storage", "model", "registry.json"
)


@lru_cache(maxsize=1)
def _load() -> dict:
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_models() -> list[dict]:
    """모델 목록. reference_urls의 첫 장(정면)이 썸네일로 쓰인다."""
    out = []
    for m in _load()["models"]:
        out.append({
            "key": m["key"],
            "name": m["name"],
            "height_cm": m["height_cm"],
            "mood": m["mood"],
            "thumbnail_url": m["reference_urls"][0],
        })
    return out


def default_key() -> str:
    return _load()["default"]


def get_model(key: str = None) -> dict:
    """키로 모델을 찾는다. 없거나 미지정이면 기본 모델."""
    models = {m["key"]: m for m in _load()["models"]}
    return models.get(key) or models[default_key()]


def reference_urls(key: str = None) -> list[str]:
    """해당 모델의 다각도 참조 URL 목록 (정면·45도·측면)."""
    return list(get_model(key)["reference_urls"])


def model_attrs(key: str = None) -> dict:
    """프롬프트 조립용 모델 속성 (agent2 model_attrs 형식)."""
    m = get_model(key)
    return {
        "age": "late 20s",
        "hair_style": m["hair_style"],
        "mood": m["mood"],
        "fashion_style": m["fashion_style"],
    }
