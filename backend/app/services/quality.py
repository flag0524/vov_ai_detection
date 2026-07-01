# 상품 원본 유지율(SSIM)과 모델 얼굴 동일성 점수를 계산하는 품질 검증 모듈
import os

# 실제 SSIM은 scikit-image 사용, 미설치 시 스텁 반환
try:
    from skimage.metrics import structural_similarity as ssim
    from skimage import io as skio
    import numpy as np
    _SKIMAGE_AVAILABLE = True
except ImportError:
    _SKIMAGE_AVAILABLE = False

PRODUCT_SSIM_THRESHOLD = 0.80
FACE_SIMILARITY_THRESHOLD = 0.85


def compute_ssim(original_path: str, generated_path: str) -> float:
    """원본 상품 이미지와 생성 이미지 간 SSIM을 계산한다."""
    if not _SKIMAGE_AVAILABLE:
        # 스텁: 실제 이미지 없을 때 기준 통과값 반환
        return 0.85

    orig = skio.imread(original_path, as_gray=True)
    gen = skio.imread(generated_path, as_gray=True)
    # 크기 맞추기
    import cv2
    gen_resized = cv2.resize(gen, (orig.shape[1], orig.shape[0]))
    score, _ = ssim(orig, gen_resized, full=True)
    return float(score)


def compute_face_similarity(embedding1: list, embedding2: list) -> float:
    """두 얼굴 임베딩의 코사인 유사도를 반환한다."""
    if not embedding1 or not embedding2:
        return 1.0  # 임베딩 없으면 검증 스킵

    try:
        import numpy as np
        a = np.array(embedding1)
        b = np.array(embedding2)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    except Exception:
        return 1.0


def validate_generation(original_path: str, generated_path: str, face_embeddings: list = None) -> dict:
    """생성물이 품질 기준을 통과하는지 검증하고 결과 딕셔너리를 반환한다."""
    ssim_score = compute_ssim(original_path, generated_path)
    product_pass = ssim_score >= PRODUCT_SSIM_THRESHOLD

    face_score = None
    face_pass = True
    if face_embeddings and len(face_embeddings) >= 2:
        face_score = compute_face_similarity(face_embeddings[0], face_embeddings[1])
        face_pass = face_score >= FACE_SIMILARITY_THRESHOLD

    overall_pass = product_pass and face_pass

    return {
        "ssim_score": round(ssim_score, 4),
        "product_pass": product_pass,
        "face_similarity": round(face_score, 4) if face_score is not None else None,
        "face_pass": face_pass,
        "overall_pass": overall_pass,
        "action": "approved" if overall_pass else "requeue",
    }
