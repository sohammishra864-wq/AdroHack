"""I0: decode any claim photo to RGB, run the quality gate, cache by sha256."""
from __future__ import annotations

import hashlib
import io
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageOps

from . import config

try:  # HEIC/HEIF support; optional so the rest works without it
    import pillow_heif

    pillow_heif.register_heif_opener()
except ImportError:
    pass

MAX_SIDE = 1024

# IJG standard luminance table (JPEG Annex K); PIL scales it by quality the same way.
STD_LUMA = [
    16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55,
    14, 13, 16, 24, 40, 57, 69, 56, 14, 17, 22, 29, 51, 87, 80, 62,
    18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
    49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99,
]
_STD_LUMA_SUM = sum(STD_LUMA)


@dataclass
class Prepared:
    path: str
    sha256: str
    data: bytes                  # original bytes, for C2PA / EXIF / JPEG-table checks
    fmt: str                     # PIL format: JPEG, PNG, HEIF, WEBP, …
    orig_size: tuple[int, int]
    rgb: Image.Image             # orientation-fixed, long side ≤ MAX_SIDE
    exif: Image.Exif
    jpeg_quality: int | None
    quality_flag: bool
    quality_reasons: list[str]


def estimate_jpeg_quality(img: Image.Image) -> int | None:
    """Invert IJG quality scaling from the luminance table. None if not a JPEG."""
    q = getattr(img, "quantization", None)
    if not q or 0 not in q:
        return None
    scale = 100 * sum(q[0]) / _STD_LUMA_SUM
    est = 5000 / scale if scale > 100 else (200 - scale) / 2
    return max(1, min(100, round(est)))


def laplacian_var(rgb: Image.Image) -> float:
    g = np.asarray(rgb.convert("L"), dtype=np.float32)
    lap = 4 * g[1:-1, 1:-1] - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


_CACHE_MAX = 32  # training/eval stream thousands of images through prepare()
_cache: OrderedDict[str, Prepared] = OrderedDict()


def prepare(path: str) -> Prepared:
    data = open(path, "rb").read()
    sha = hashlib.sha256(data).hexdigest()
    if sha in _cache:
        _cache.move_to_end(sha)
        return _cache[sha]

    img = Image.open(io.BytesIO(data))
    fmt, orig_size, exif = img.format or "", img.size, img.getexif()
    jpeg_q = estimate_jpeg_quality(img)
    rgb = ImageOps.exif_transpose(img).convert("RGB")
    rgb.thumbnail((MAX_SIDE, MAX_SIDE))

    g = config.cfg("thresholds")["quality_gate"]
    reasons = []
    if min(orig_size) < g["min_short_side_px"]:
        reasons.append(f"image is only {orig_size[0]}×{orig_size[1]} px "
                       f"(below {g['min_short_side_px']} px)")
    if jpeg_q is not None and jpeg_q < g["min_est_jpeg_quality"]:
        reasons.append(f"heavily compressed (JPEG quality ≈{jpeg_q})")
    if laplacian_var(rgb) < g["min_laplacian_var"]:
        reasons.append("image is very blurry")

    prep = Prepared(path, sha, data, fmt, orig_size, rgb, exif, jpeg_q, bool(reasons), reasons)
    _cache[sha] = prep
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return prep
