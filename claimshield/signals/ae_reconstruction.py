"""I1 (deep tier): AEROBLADE reconstruction test (Ricker et al., CVPR 2024). Encode→decode
through the SD VAE(s); diffusion-generated pixels come back with LOWER LPIPS error (VGG
layer 2) than camera pixels. Min distance over VAEs: 1 on CPU (SD1.5), SD1.5+SDXL+Flux on
GPU. Always on, supporting evidence: confidence capped (thresholds.yaml), fixed card text.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from .. import config
from ..contracts import Signal
from . import vae

NAME = "ae_reconstruction"
TEXT = ("Reconstruction test: {} error. Most informative for diffusion-generated images; "
        "treated as supporting evidence.")
VAE_ORDER = ("sd15", "sdxl", "flux")


@lru_cache(maxsize=1)
def lpips_vgg():
    import lpips

    return lpips.LPIPS(net="vgg", verbose=False).to(config.device()).eval()


def _vaes() -> tuple[str, ...]:
    R = config.cfg("runtime")
    return VAE_ORDER[:R["vae_count_gpu" if config.device() == "cuda" else "vae_count_cpu"]]


def distance(rgb, name: str, px: int) -> tuple[float, np.ndarray]:
    """LPIPS layer-2 distance between x and its reconstruction + the spatial map (h×w)."""
    import lpips
    import torch

    x, y = vae.reconstruct(rgb, px, name)
    m = lpips_vgg()
    with torch.inference_mode():
        f0, f1 = m.net(m.scaling_layer(x)), m.net(m.scaling_layer(y.clamp(-1, 1)))
        d = (lpips.normalize_tensor(f0[1]) - lpips.normalize_tensor(f1[1])) ** 2
        spatial = m.lins[1](d)[0, 0].float().cpu().numpy()
    return float(spatial.mean()), spatial


def warm():
    for n in _vaes():
        vae.load(n)
    lpips_vgg()


def run(prep) -> Signal:
    C = config.cfg("thresholds")[NAME]
    px = C["input_px_gpu" if config.device() == "cuda" else "input_px_cpu"]
    per = {n: distance(prep.rgb, n, px) for n in _vaes()}
    best = min(per, key=lambda n: per[n][0])
    d, spatial = per[best]
    score = float(1 / (1 + np.exp((d - C["center"]) / C["scale"])))
    conf = min(C["confidence_cap"], max(0.3, abs(2 * score - 1)))
    patch = cv2.resize(vae.relative_low(spatial), prep.rgb.size)
    return Signal(NAME, score, conf, TEXT.format("low" if score >= 0.5 else "high"),
                  {"distance": d, "vae": best, "per_vae": {n: v[0] for n, v in per.items()},
                   "patch_map": patch}, tier="deep")
