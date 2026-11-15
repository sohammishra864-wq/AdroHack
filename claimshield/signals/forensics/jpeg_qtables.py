"""JPEG quantization tables: camera-vs-software tables and double compression (JPEG ghost).

Standard IJG tables on a file whose EXIF names a camera → it was re-encoded by software.
Double compression alone is normal for forwarded photos, so it is weak evidence.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from PIL.ExifTags import Base

from ...contracts import Signal
from ...preprocess import STD_LUMA

NAME = "jpeg_qtables"
GHOST_QS = list(range(40, 100, 5))
CROP = 512


def ijg_table(q: int) -> list[int]:
    scale = 5000 / q if q < 50 else 200 - 2 * q
    return [min(255, max(1, int((s * scale + 50) // 100))) for s in STD_LUMA]


def is_standard(table: list[int], q: int) -> bool:
    t = sorted(table)  # order-free: PIL may report zigzag or natural order
    return any(t == sorted(ijg_table(k)) for k in (q - 1, q, q + 1) if 1 <= k <= 100)


def ghost_quality(gray: Image.Image, q_now: int) -> int | None:
    """Earlier compression quality if the resave-error curve dips below the current one."""
    a = np.asarray(gray, np.float32)
    d = []
    for q in GHOST_QS:
        buf = io.BytesIO()
        gray.save(buf, "JPEG", quality=q)
        d.append(float(((np.asarray(Image.open(buf), np.float32) - a) ** 2).mean()))
    d = np.array(d) / (max(d) or 1)
    # ponytail: fixed dip heuristic; calibrate on the q90/q70/q50 manifest rows.
    for i in range(1, len(GHOST_QS) - 1):
        if GHOST_QS[i] < q_now - 5 and d[i] < 0.8 * min(d[i - 1], d[i + 1]):
            return GHOST_QS[i]
    return None


def run(prep) -> Signal:
    if prep.fmt != "JPEG" or prep.jpeg_quality is None:
        return Signal(NAME, None, 0.0, f"Not applicable: {prep.fmt or 'this'} file has no JPEG "
                      "quantization tables.", applicable=False)

    img = Image.open(io.BytesIO(prep.data))
    q = prep.jpeg_quality
    standard = is_standard(list(img.quantization[0]), q)
    g = img.convert("L")
    x0, y0 = max(0, (g.width // 2 - CROP // 2) // 8 * 8), max(0, (g.height // 2 - CROP // 2) // 8 * 8)
    q_prev = ghost_quality(g.crop((x0, y0, x0 + CROP, y0 + CROP)), q)
    make = str(prep.exif.get(Base.Make, "")).strip("\x00 ")
    ev = {"quality": q, "standard_tables": standard, "earlier_quality": q_prev, "make": make}

    if standard and make:
        return Signal(NAME, 0.65, 0.4, f"Metadata says the photo came from a {make} camera, but "
                      f"it was re-encoded by standard software (quality ≈{q}).", ev)
    if q_prev:
        return Signal(NAME, 0.55, 0.25, f"Compressed at least twice (earlier quality ≈{q_prev}, "
                      f"now ≈{q}). Normal for forwarded photos, so weak evidence.", ev)
    kind = "software" if standard else "camera-style"
    return Signal(NAME, 0.3, 0.3, f"Single compression at quality ≈{q} with {kind} tables.", ev)
