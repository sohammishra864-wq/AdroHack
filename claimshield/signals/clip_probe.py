"""I2: frozen CLIP ViT-L/14 features + logistic head (UnivFD-style). Head trained by
scripts/train_heads.py on heldout=0 rows; Flux is never seen.
"""
from __future__ import annotations

import pickle
import threading
from functools import lru_cache

import numpy as np

from .. import config
from ..contracts import Signal

NAME = "clip_probe"
HEAD = "heads/clip_probe.pkl"
_lock = threading.Lock()   # probe and family map share one feature pass per image
_feats: dict[str, np.ndarray] = {}


@lru_cache(maxsize=1)
def model():
    import open_clip

    c = config.cfg("runtime")["clip"]
    m, _, pre = open_clip.create_model_and_transforms(
        c["arch"], pretrained=c["pretrained"], device=config.device(),
        cache_dir=str(config.models_dir() / "clip"))
    return m.eval(), pre


def embed(rgb) -> np.ndarray:
    import torch

    m, pre = model()
    with torch.inference_mode():
        f = m.encode_image(pre(rgb).unsqueeze(0).to(config.device()))
        f = f / f.norm(dim=-1, keepdim=True)
    return f[0].float().cpu().numpy()


def cache_path(sha: str):
    """Disk cache keyed by model too, so an arch/weights change never reads stale features."""
    c = config.cfg("runtime")["clip"]
    return config.ROOT / "data" / "cache" / "clip" / f"{c['arch']}-{c['pretrained']}" / f"{sha}.npy"


def features(prep) -> np.ndarray:
    """L2-normalised CLIP features, cached in memory and on disk by sha256."""
    with _lock:
        if prep.sha256 not in _feats:
            disk = cache_path(prep.sha256)
            if disk.exists():
                f = np.load(disk)
            else:
                f = embed(prep.rgb)
                disk.parent.mkdir(parents=True, exist_ok=True)
                np.save(disk, f)
            if len(_feats) > 256:
                _feats.clear()
            _feats[prep.sha256] = f
        return _feats[prep.sha256]


def load_head(rel: str):
    p = config.models_dir() / rel
    if not p.exists():
        raise FileNotFoundError(f"{p} missing — run scripts/train_heads.py")
    return pickle.loads(p.read_bytes())


@lru_cache(maxsize=1)
def head():
    return load_head(HEAD)


def warm():
    model(), head()


def run(prep) -> Signal:
    p = float(head().predict_proba(features(prep)[None])[0, 1])
    reason = (f"Visual-feature probe: looks AI-generated ({p:.2f})." if p >= 0.5 else
              f"Visual-feature probe: looks like a real camera photo ({1 - p:.2f}).")
    return Signal(NAME, p, max(0.3, abs(2 * p - 1)), reason, {"p_fake": p})
