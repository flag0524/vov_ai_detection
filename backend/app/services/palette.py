# 업로드 상품 이미지에서 지배 색상 팔레트를 추출 (외부 API 없음, PIL 양자화 — ADR-012 준수)
import io

from PIL import Image


def extract_palette(image_bytes: bytes, n: int = 5) -> list[dict]:
    """이미지 픽셀에서 지배 색상 n개를 추출해 [{hex, ratio}] 리스트로 반환한다.
    MEDIANCUT 양자화로 결정적이며 Vision 모델/외부 API를 쓰지 않는다.
    ratio는 해당 색이 차지하는 픽셀 비중(0~1), 큰 순으로 정렬."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((100, 100))
    quantized = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)

    palette = quantized.getpalette()  # [r,g,b, r,g,b, ...] 인덱스 순
    counts = quantized.getcolors()  # [(픽셀수, 팔레트인덱스), ...]
    if not counts:
        return []

    total = sum(c for c, _ in counts)
    result = []
    for count, idx in sorted(counts, key=lambda x: x[0], reverse=True):
        r, g, b = palette[idx * 3 : idx * 3 + 3]
        result.append({"hex": f"#{r:02X}{g:02X}{b:02X}", "ratio": round(count / total, 3)})
    return result
