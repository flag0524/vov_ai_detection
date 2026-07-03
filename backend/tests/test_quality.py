# tests.md Phase 2/6 품질 게이트(SSIM·얼굴 유사도·재생성 루프) 단위 테스트
import numpy as np
import pytest
from unittest.mock import patch

from app.services import quality


@pytest.fixture()
def image_pair(tmp_path):
    """동일 이미지 1쌍과 크게 다른 이미지 1장을 파일로 저장해 경로 반환."""
    from skimage import io as skio
    rng = np.random.default_rng(42)
    original = (rng.random((64, 64)) * 255).astype(np.uint8)
    different = 255 - original  # 반전 → SSIM 낮음

    orig_path = tmp_path / "orig.png"
    same_path = tmp_path / "same.png"
    diff_path = tmp_path / "diff.png"
    skio.imsave(orig_path, original)
    skio.imsave(same_path, original)
    skio.imsave(diff_path, different)
    return str(orig_path), str(same_path), str(diff_path)


def test_ssim_identical_images_is_one(image_pair):
    """tests.md Phase 2: 동일 이미지 SSIM = 1.0 (실계산 확인)"""
    orig, same, _ = image_pair
    assert quality.compute_ssim(orig, same) == pytest.approx(1.0)


def test_ssim_different_images_below_threshold(image_pair):
    """tests.md Phase 2: 반전 이미지는 SSIM < 0.80 → 게이트 미달"""
    orig, _, diff = image_pair
    score = quality.compute_ssim(orig, diff)
    assert score < quality.PRODUCT_SSIM_THRESHOLD


def test_validate_generation_requeues_on_low_ssim(image_pair):
    """불변 제약: 기준 미달 산출물은 action=requeue"""
    orig, _, diff = image_pair
    result = quality.validate_generation(orig, diff)
    assert result["overall_pass"] is False
    assert result["action"] == "requeue"


def test_face_similarity_gate():
    """tests.md 공통 게이트: 얼굴 임베딩 유사도 ≥ 0.85"""
    same = [1.0, 0.0, 0.0]
    similar = [0.95, 0.31, 0.0]   # cos ≈ 0.95
    other = [0.0, 1.0, 0.0]       # cos = 0
    assert quality.compute_face_similarity(same, same) == pytest.approx(1.0)
    assert quality.compute_face_similarity(same, similar) >= 0.85
    assert quality.compute_face_similarity(same, other) < 0.85


def test_face_gate_skipped_without_embeddings(image_pair):
    """검수 임베딩이 없으면 얼굴 게이트는 스킵(face_pass=True)"""
    orig, same, _ = image_pair
    result = quality.validate_generation(orig, same, face_embeddings=None)
    assert result["face_similarity"] is None
    assert result["face_pass"] is True


# --- Phase 6: 재생성 루프 ---

def test_quality_gate_retries_until_pass():
    """tests.md Phase 6: 기준 미달 → 재생성 → 재시도 후 기준 통과"""
    with patch.object(quality, "compute_ssim", side_effect=[0.5, 0.5, 0.9]):
        _, q, attempts = quality.run_with_quality_gate(
            generate_fn=lambda: {"image_url": "stub"},
            original_path="x.png",
            max_attempts=3,
        )
    assert attempts == 3
    assert q["overall_pass"] is True


def test_quality_gate_fails_after_max_attempts():
    """tests.md Phase 6: max_attempts 소진 시 overall_pass=False로 종료"""
    with patch.object(quality, "compute_ssim", return_value=0.5):
        _, q, attempts = quality.run_with_quality_gate(
            generate_fn=lambda: {"image_url": "stub"},
            original_path="x.png",
            max_attempts=2,
        )
    assert attempts == 2
    assert q["overall_pass"] is False
    assert q["action"] == "requeue"


def test_quality_gate_passes_first_try():
    """기준 통과 시 재생성 없이 1회로 종료"""
    with patch.object(quality, "compute_ssim", return_value=0.95):
        _, q, attempts = quality.run_with_quality_gate(
            generate_fn=lambda: {"image_url": "stub"},
            original_path="x.png",
        )
    assert attempts == 1
    assert q["overall_pass"] is True
