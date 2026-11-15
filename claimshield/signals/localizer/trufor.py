"""TruFor (Guillaro et al., CVPR 2023). Research licence → prototype only; swappable via
`localizer.impl`. Needs the official code vendored and weights under CLAIMSHIELD_MODELS_DIR
at the paths in runtime.yaml `trufor`.

UNVERIFIED: written from the upstream test script's call pattern, not run against the
vendored code yet (README).
"""
from __future__ import annotations

import sys

import numpy as np

from ... import config
from .base import LocResult

MAX_PX = 768


class TruFor:
    name = "trufor"

    def __init__(self):
        c, root = config.cfg("runtime")["trufor"], config.models_dir()
        self.src, self.cfg, self.weights = (root / c[k] for k in ("src", "cfg", "weights"))
        missing = [str(p) for p in (self.src, self.cfg, self.weights) if not p.exists()]
        if missing:
            raise FileNotFoundError("TruFor not installed; missing: " + ", ".join(missing))
        self._model = None

    def warm(self):
        if self._model is None:
            import torch

            sys.path.insert(0, str(self.src))
            from config import _C as tcfg  # upstream module names
            from models.cmx.builder_np_conf import myEncoderDecoder

            tcfg.defrost()
            tcfg.merge_from_file(str(self.cfg))
            tcfg.freeze()
            m = myEncoderDecoder(cfg=tcfg)
            ck = torch.load(self.weights, map_location=config.device(), weights_only=False)
            m.load_state_dict(ck["state_dict"])
            self._model = m.to(config.device()).eval()

    def __call__(self, rgb) -> LocResult:
        import torch
        import torch.nn.functional as F

        self.warm()
        img = rgb.copy()
        img.thumbnail((MAX_PX, MAX_PX))
        x = torch.tensor(np.asarray(img).transpose(2, 0, 1), dtype=torch.float32)[None] / 256.0
        with torch.inference_mode():
            pred, conf, det, _ = self._model(x.to(config.device()))
        heat = F.softmax(pred[0], dim=0)[1].cpu().numpy()
        rel = torch.sigmoid(conf[0])[0].cpu().numpy() if conf is not None else None
        integrity = float(torch.sigmoid(det).item()) if det is not None else float(heat.max())
        return LocResult(heat, rel, integrity)
