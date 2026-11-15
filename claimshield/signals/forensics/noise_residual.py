"""Noise residual: per-block noise level vs the rest of the photo. A pasted or inpainted
area usually carries a different noise level. Also feeds the fallback localizer + regions.
"""
from __future__ import annotations

import cv2
import numpy as np

from ... import config
from ...contracts import Signal

NAME = "noise_residual"
MIN_BLOCKS = 16


def block_z(rgb, block: int, max_texture: float) -> np.ndarray:
    """Robust z-score of log noise level per block (0 where the block is unusable)."""
    g8 = np.asarray(rgb.convert("L"))
    g = g8.astype(np.float32)
    res = g - cv2.medianBlur(g8, 3).astype(np.float32)
    smooth = cv2.GaussianBlur(g, (0, 0), 3)  # content texture, mostly free of noise
    H, W = g.shape[0] // block * block, g.shape[1] // block * block
    if H == 0 or W == 0:
        return np.zeros((0, 0), np.float32)

    def blocks(a):
        return a[:H, :W].reshape(H // block, block, W // block, block)

    noise = np.log(blocks(res).std(axis=(1, 3)) + 1e-3)
    mean = blocks(g).mean(axis=(1, 3))
    valid = (blocks(smooth).std(axis=(1, 3)) <= max_texture) & (mean > 10) & (mean < 245)
    if valid.sum() < MIN_BLOCKS:
        return np.zeros_like(noise)
    med = np.median(noise[valid])
    mad = max(1.4826 * np.median(np.abs(noise[valid] - med)), 0.05)  # floor: flat test images
    return np.where(valid, (noise - med) / mad, 0).astype(np.float32)


def run(prep) -> Signal:
    c = config.cfg("thresholds")["noise_residual"]
    z = block_z(prep.rgb, c["block_px"], c["max_texture_std"])
    if z.size < MIN_BLOCKS or not z.any():
        return Signal(NAME, None, 0.0, "Not applicable: too few smooth areas to compare "
                      "noise levels.", applicable=False)

    out = (np.abs(z) > c["z_outlier"]).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(out, connectivity=8)
    largest = stats[1:, cv2.CC_STAT_AREA].max() / z.size if n > 1 else 0.0
    ev = {"block_z": z, "block_px": c["block_px"], "largest_frac": float(largest)}
    if largest >= c["min_cluster_frac"]:
        return Signal(NAME, 0.7, 0.35, f"An area covering {largest:.0%} of the photo has a "
                      "different noise level than the rest — consistent with pasting or "
                      "inpainting.", ev)
    return Signal(NAME, 0.3, 0.25, "Noise level is consistent across the photo.", ev)
