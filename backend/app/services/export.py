# 생성 이미지를 인스타그램 포맷(Feed/Reel/Story)으로 리사이즈·크롭하는 모듈
import os

from PIL import Image

# PRD FR-5 — 인스타그램 채널별 규격
FORMATS = {
    "feed": (1080, 1350),   # 4:5
    "reel": (1080, 1920),   # 9:16
    "story": (1080, 1920),  # 9:16
}


def export_instagram(source_path: str, output_dir: str, formats: list = None) -> dict:
    """원본 이미지를 지정 포맷들로 센터 크롭 + 리사이즈해 저장하고 경로 맵을 반환한다."""
    formats = formats or list(FORMATS.keys())
    unknown = [f for f in formats if f not in FORMATS]
    if unknown:
        raise ValueError(f"지원하지 않는 포맷: {unknown} (지원: {list(FORMATS.keys())})")

    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_path))[0]

    with Image.open(source_path) as img:
        img = img.convert("RGB")
        results = {}
        for fmt in formats:
            target_w, target_h = FORMATS[fmt]
            resized = _center_crop_resize(img, target_w, target_h)
            out_path = os.path.join(output_dir, f"{base}_{fmt}_{target_w}x{target_h}.jpg")
            resized.save(out_path, "JPEG", quality=92)
            results[fmt] = out_path
    return results


def _center_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """비율이 다르면 넘치는 축을 중앙 기준으로 잘라낸 뒤 목표 크기로 리사이즈한다."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # 원본이 더 넓음 → 좌우 크롭
        crop_w = int(src_h * target_ratio)
        left = (src_w - crop_w) // 2
        box = (left, 0, left + crop_w, src_h)
    else:
        # 원본이 더 높음 → 상하 크롭
        crop_h = int(src_w / target_ratio)
        top = (src_h - crop_h) // 2
        box = (0, top, src_w, top + crop_h)

    return img.crop(box).resize((target_w, target_h), Image.LANCZOS)
