"""Identity lane: InsightFace buffalo_l, ArcFace cosine between the ID photo and the selfie.
No morph heuristic (ARCHITECTURE). Score = probability of a mismatch around the threshold.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from ... import config
from ...contracts import Signal

NAME = "face_match"
MIN_DET = 0.5
SOFTNESS = 0.05  # cosine units; how sharply the score turns around the threshold


@lru_cache(maxsize=1)
def model():
    from insightface.app import FaceAnalysis

    cuda = config.device() == "cuda"
    app = FaceAnalysis(name="buffalo_l", root=str(config.models_dir() / "insightface"),
                       providers=["CUDAExecutionProvider" if cuda else "CPUExecutionProvider"])
    app.prepare(ctx_id=0 if cuda else -1, det_size=(640, 640))
    return app


def warm():
    model()


def embed(rgb) -> tuple[np.ndarray, float] | None:
    """Largest face → (L2-normalised embedding, detection score); None if no face."""
    faces = model().get(np.asarray(rgb)[:, :, ::-1].copy())  # insightface wants BGR
    if not faces:
        return None
    f = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
    return f.normed_embedding, float(f.det_score)


def run(id_rgb, selfie_rgb) -> Signal:
    a, b = embed(id_rgb), embed(selfie_rgb)
    missing = [w for w, e in (("the ID", a), ("the selfie", b)) if e is None or e[1] < MIN_DET]
    if missing:
        return Signal(NAME, None, 0.0, f"Not applicable: no clear face found in {' or '.join(missing)}.",
                      applicable=False, tier="identity")
    cos = float(np.dot(a[0], b[0]))
    thr = config.cfg("thresholds")["face_match"]["cosine_mismatch_below"]
    score = float(1 / (1 + np.exp((cos - thr) / SOFTNESS)))
    ev = {"cosine": cos, "threshold": thr, "det_scores": (a[1], b[1])}
    reason = (f"The selfie does not match the ID photo (similarity {cos:.2f}, match needs {thr:.2f})."
              if cos < thr else f"The selfie matches the ID photo (similarity {cos:.2f}).")
    return Signal(NAME, score, min(a[1], b[1]) * 0.9, reason, ev, tier="identity")
