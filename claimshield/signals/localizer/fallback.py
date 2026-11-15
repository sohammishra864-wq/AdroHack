"""Union localizer (our own, no licence issue): mini-AE low-error map ∪ noise-residual
blocks. Reliability = agreement of the two, so the Regions stage keeps only areas where
both point the same way. Used when TruFor weights are unavailable (configs/thresholds.yaml).
"""
from __future__ import annotations

import cv2
import numpy as np

from ... import config
from .. import vae
from ..forensics.noise_residual import block_z
from .base import LocResult

AE_PX = 256


class Fallback:
    name = "fallback"

    def warm(self):
        vae.load()

    def __call__(self, rgb) -> LocResult:
        c = config.cfg("thresholds")["noise_residual"]
        ae = vae.low_error_map(rgb, AE_PX)
        z = block_z(rgb, c["block_px"], c["max_texture_std"])
        nz = np.zeros(ae.shape, np.float32)
        if z.size:
            b = c["block_px"]
            up = np.kron(np.clip(np.abs(z) / (2 * c["z_outlier"]), 0, 1), np.ones((b, b)))
            nz[:up.shape[0], :up.shape[1]] = up  # 0.5 exactly at the outlier threshold
        heat = np.maximum(ae, nz)
        rel = 1 - np.abs(ae - nz)
        # ponytail: integrity = 99th pct of agreed evidence; calibrate on the calib split.
        return LocResult(heat, rel, float(np.percentile(heat * rel, 99)))
