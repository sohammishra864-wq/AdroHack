"""Copy-move: SIFT self-matching (g2NN ratio) + RANSAC on the matched pairs."""
from __future__ import annotations

import cv2
import numpy as np

from ... import config
from ...contracts import Signal

NAME = "copy_move"


def find_pairs(gray: np.ndarray, ratio: float, min_shift: float) -> np.ndarray:
    """N×4 array of (x1, y1, x2, y2) keypoint pairs that look like copies of each other."""
    kp, des = cv2.SIFT_create(nfeatures=3000).detectAndCompute(gray, None)
    if des is None or len(kp) < 3:
        return np.empty((0, 4), np.float32)
    seen, pairs = set(), []
    for m in cv2.BFMatcher(cv2.NORM_L2).knnMatch(des, des, k=3):
        # drop the self-match; with an exact copy it ties at distance 0 and may not be first
        m = [x for x in m if x.trainIdx != x.queryIdx]
        if len(m) < 2:
            continue
        b, c = m[:2]
        key = tuple(sorted((b.queryIdx, b.trainIdx)))
        if b.distance >= ratio * c.distance or key in seen:
            continue
        p, q = kp[b.queryIdx].pt, kp[b.trainIdx].pt
        if np.hypot(p[0] - q[0], p[1] - q[1]) > min_shift:
            seen.add(key)
            pairs.append((*p, *q) if p < q else (*q, *p))  # canonical direction for RANSAC
    return np.array(pairs, np.float32).reshape(-1, 4)


def _box(pts: np.ndarray, pad: int = 8) -> list[int]:
    x1, y1 = pts.min(0) - pad
    x2, y2 = pts.max(0) + pad
    return [int(max(0, x1)), int(max(0, y1)), int(x2), int(y2)]


def run(prep) -> Signal:
    c = config.cfg("thresholds")["copy_move"]
    gray = np.asarray(prep.rgb.convert("L"))
    pairs = find_pairs(gray, c["ratio"], c["min_shift_px"])
    if len(pairs) >= c["min_matches"]:
        pts = lambda a: np.ascontiguousarray(a, np.float32).reshape(-1, 1, 2)  # noqa: E731  OpenCV 5 rejects strided float64
        _, inl = cv2.estimateAffinePartial2D(pts(pairs[:, :2]), pts(pairs[:, 2:]), method=cv2.RANSAC,
                                             ransacReprojThreshold=3.0)
        keep = pairs[inl.ravel() == 1] if inl is not None else pairs[:0]
        if len(keep) >= c["min_matches"]:
            boxes = [_box(keep[:, :2]), _box(keep[:, 2:])]
            return Signal(NAME, 0.85, 0.6, f"Two areas of the photo are copies of each other "
                          f"({len(keep)} matching points).", {"boxes": boxes, "n": len(keep)})
    return Signal(NAME, 0.3, 0.3, "No duplicated areas found.", {"boxes": [], "n": len(pairs)})
