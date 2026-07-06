# 인스타 포맷 산출(export)과 Naturalness 프롬프트 내장(B-1/B-3) 검증 테스트
import pytest
from PIL import Image

from app.services.export import export_instagram, FORMATS


@pytest.fixture()
def source_image(tmp_path):
    """가로로 긴 원본 이미지 (크롭이 실제로 일어나도록 2000x1000)."""
    path = tmp_path / "src.jpg"
    Image.new("RGB", (2000, 1000), color=(200, 50, 100)).save(path)
    return str(path)


def test_export_all_formats_exact_sizes(source_image, tmp_path):
    """PRD FR-5: Feed 1080x1350, Reel/Story 1080x1920 규격 정확히 산출"""
    out = export_instagram(source_image, str(tmp_path / "out"))
    assert set(out.keys()) == {"feed", "reel", "story"}
    for fmt, path in out.items():
        with Image.open(path) as img:
            assert img.size == FORMATS[fmt], f"{fmt} 크기 불일치"


def test_export_selected_format_only(source_image, tmp_path):
    out = export_instagram(source_image, str(tmp_path / "out"), formats=["feed"])
    assert list(out.keys()) == ["feed"]


def test_export_rejects_unknown_format(source_image, tmp_path):
    with pytest.raises(ValueError):
        export_instagram(source_image, str(tmp_path / "out"), formats=["youtube"])


def test_export_portrait_source(tmp_path):
    """세로로 긴 원본도 상하 크롭으로 정확한 규격 산출"""
    src = tmp_path / "tall.jpg"
    Image.new("RGB", (500, 3000), color=(10, 20, 30)).save(src)
    out = export_instagram(str(src), str(tmp_path / "out"), formats=["reel"])
    with Image.open(out["reel"]) as img:
        assert img.size == (1080, 1920)


# --- B-1: Naturalness 프롬프트 내장 (PRD FR-7 / TRD §5·§6) ---

def test_agent2_prompt_includes_naturalness():
    """이미지 프롬프트에 자연스러움 지시어·Negative Prompt 포함"""
    from agents.agent2_prompt_engineer import (
        generate_photoshoot_prompt, NATURALNESS_PROMPT, NATURALNESS_NEGATIVE,
    )
    r = generate_photoshoot_prompt({"category": "원피스"}, {"mood": "elegant"})
    assert NATURALNESS_PROMPT in r["prompt"]
    assert NATURALNESS_NEGATIVE in r["negative_prompt"]


def test_agent4_naturalness_constants_defined():
    """영상 모션 프롬프트 상수에 TRD §6 필수 지시어 포함"""
    from agents.agent4_video_creator import (
        NATURALNESS_MOTION_PROMPT, NATURALNESS_MOTION_NEGATIVE,
    )
    assert "natural human walking rhythm" in NATURALNESS_MOTION_PROMPT
    assert "no expression morphing" in NATURALNESS_MOTION_PROMPT
    assert "robotic movement" in NATURALNESS_MOTION_NEGATIVE
    assert "face morphing" in NATURALNESS_MOTION_NEGATIVE
