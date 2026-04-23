from dataclasses import dataclass
from io import BytesIO

import cv2
import imagehash
import numpy as np
from PIL import Image

# Laplacian variance threshold for accepting an upload (best score across strategies).
BLUR_MIN_SCORE = 100.0
# Max dimension after upscale used for blur metrics (memory / speed guard).
_MAX_BLUR_CHECK_SIDE = 4500


def _decode_bgr(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image bytes")
    return img


def _laplacian_variance_bgr(bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def check_blur(image_bytes: bytes) -> float:
    """Return Laplacian variance on the original decode (no zoom)."""
    return _laplacian_variance_bgr(_decode_bgr(image_bytes))


@dataclass(frozen=True)
class BlurAssessment:
    """Blur metrics: original plus synthetic 'zoom' (upscale) passes for document photos."""

    effective_score: float
    original_score: float
    winning_strategy: str
    breakdown: tuple[tuple[str, float], ...]
    minimum: float = BLUR_MIN_SCORE

    @property
    def passed(self) -> bool:
        return self.effective_score >= self.minimum


def _workspace_for_zoom_metrics(bgr: np.ndarray) -> np.ndarray:
    """
    iREV / scanned sheets are often very wide. Upscaled dimensions must stay
    under _MAX_BLUR_CHECK_SIDE or every zoom level is skipped. Shrink (AREA)
    so longest_edge * 2.5 fits, then zoom metrics are meaningful.
    """
    h, w = bgr.shape[:2]
    longest = max(h, w)
    max_zoom = 2.5
    limit = longest * max_zoom
    if limit <= _MAX_BLUR_CHECK_SIDE:
        return bgr
    scale = _MAX_BLUR_CHECK_SIDE / limit
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    return cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)


def assess_blur_with_zoom(image_bytes: bytes) -> BlurAssessment:
    """
    Score sharpness on the full-resolution decode, plus a workspace pipeline.

    Large images: all zoom factors were previously skipped when
    max(width,height) * 1.25 exceeded the cap — only a single score appeared.
    We downscale into a workspace when needed, then apply the same zoom
    ladder. Pass if either native or workspace best meets BLUR_MIN_SCORE.

    Stored upload bytes are unchanged; metrics are diagnostic only.
    """
    img_full = _decode_bgr(image_bytes)
    original_native = _laplacian_variance_bgr(img_full)

    img = _workspace_for_zoom_metrics(img_full)
    breakdown: list[tuple[str, float]] = [
        ("original_native", original_native),
        ("workspace_base", _laplacian_variance_bgr(img)),
    ]
    h, w = img.shape[:2]
    # Include ~20% zoom (1.2×): matches “zoom in 20%” where many iREV sheets read clearly.
    for scale in (1.2, 1.25, 1.5, 2.0, 2.5):
        nw = int(round(w * scale))
        nh = int(round(h * scale))
        if max(nw, nh) > _MAX_BLUR_CHECK_SIDE:
            continue
        zoomed = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_CUBIC)
        breakdown.append((f"zoom_{scale:g}x", _laplacian_variance_bgr(zoomed)))

    # Workspace-only best (apples-to-apples across zooms)
    ws_entries = [x for x in breakdown if x[0] != "original_native"]
    best_ws_name, best_ws_score = max(ws_entries, key=lambda x: x[1])

    effective_score = max(original_native, best_ws_score)
    if original_native >= best_ws_score:
        winning_strategy = "original_native"
    else:
        winning_strategy = best_ws_name

    return BlurAssessment(
        effective_score=effective_score,
        original_score=original_native,
        winning_strategy=winning_strategy,
        breakdown=tuple(breakdown),
        minimum=BLUR_MIN_SCORE,
    )


def calculate_phash(image_bytes: bytes) -> str:
    """Return perceptual hash as a hex string (ImageHash / pHash)."""
    image = Image.open(BytesIO(image_bytes))
    try:
        return str(imagehash.phash(image))
    finally:
        image.close()


def phash_hamming(a_hex: str, b_hex: str) -> int:
    ha = imagehash.hex_to_hash(a_hex)
    hb = imagehash.hex_to_hash(b_hex)
    return ha - hb
