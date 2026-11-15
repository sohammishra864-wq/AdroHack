"""SD1.5 VAE encode→decode, shared by the fallback localizer (mini-AE, 256 px) and the
deep-tier AE reconstruction signal. Generated / inpainted pixels reconstruct with LOWER
error than camera pixels (AEROBLADE, Ricker et al. CVPR 2024).
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from .. import config


@lru_cache(maxsize=None)
def load(name: str = "sd15"):
    """name ∈ runtime.yaml `vaes` (sd15 on CPU; sd15, sdxl, flux on GPU)."""
    from diffusers import AutoencoderKL

    local = config.models_dir() / "vae" / name
    if local.exists():
        vae = AutoencoderKL.from_pretrained(str(local))
    else:
        c = config.cfg("runtime")["vaes"][name]
        vae = AutoencoderKL.from_pretrained(c["hf_id"], subfolder=c.get("subfolder"),
                                            cache_dir=config.hf_cache())
    return vae.to(config.device()).eval()


def reconstruct(rgb, px: int, name: str = "sd15"):
    """(x, x_hat) as 1×3×H×W tensors in [-1, 1], long side = px, sides multiple of 8."""
    import torch

    s = px / max(rgb.size)
    W, H = (max(8, round(d * s / 8) * 8) for d in rgb.size)
    x = torch.from_numpy(np.asarray(rgb.resize((W, H)), np.float32) / 127.5 - 1)
    x = x.permute(2, 0, 1)[None].to(config.device())
    vae = load(name)
    with torch.inference_mode():
        y = vae.decode(vae.encode(x).latent_dist.mode()).sample
    return x, y


def low_error_map(rgb, px: int = 256) -> np.ndarray:
    """H×W map in [0, 1] at rgb size: 1 where reconstruction error is unusually LOW."""
    x, y = reconstruct(rgb, px)
    err = (x - y).abs().mean(1)[0].float().cpu().numpy()
    return cv2.resize(relative_low(cv2.GaussianBlur(err, (0, 0), 3)), rgb.size)


def relative_low(err: np.ndarray) -> np.ndarray:
    """Error map → [0, 1], 1 where error is unusually low vs this image's own median."""
    le = np.log(err + 1e-4)
    med = np.median(le)
    mad = max(1.4826 * np.median(np.abs(le - med)), 1e-3)
    # ponytail: z=2.5 below median → 0.5; calibrate against inpaint masks (localizer IoU row).
    return np.clip((med - le) / mad / 5, 0, 1).astype(np.float32)
