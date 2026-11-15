"""I3: forgery localizer behind one interface; `thresholds.yaml: localizer.impl` switches
trufor | fallback. This module turns a LocResult into the `localizer` Signal.
"""
from __future__ import annotations

from functools import lru_cache

import cv2
import numpy as np

from ... import config
from ...contracts import Signal
from .base import Localizer, LocResult  # noqa: F401  (re-export)

NAME = "localizer"


@lru_cache(maxsize=None)
def get(impl: str) -> Localizer:
    if impl == "trufor":
        from .trufor import TruFor
        return TruFor()
    if impl == "fallback":
        from .fallback import Fallback
        return Fallback()
    raise ValueError(f"unknown localizer impl {impl!r} (trufor | fallback)")


def current() -> Localizer:
    return get(config.cfg("thresholds")["localizer"]["impl"])


def warm():
    current().warm()


def run(prep) -> Signal:
    T, B = config.cfg("thresholds")["localizer"], config.cfg("thresholds")["bands"]
    loc = current()
    r = loc(prep.rgb)
    size = prep.rgb.size
    heat = cv2.resize(r.heatmap.astype(np.float32), size)
    rel = None if r.reliability is None else cv2.resize(r.reliability.astype(np.float32), size)
    hot = heat >= 0.5
    if rel is not None:
        hot &= rel >= T["reliability_min"]
    frac = float(hot.mean())
    conf = float(rel.mean()) if rel is not None else 0.6
    ev = {"heatmap": heat, "reliability": rel, "impl": loc.name, "area_frac": frac}

    if r.integrity >= B["medium_max"]:
        why = f"likely edited area covering {frac:.0%} of the photo"
    elif r.integrity >= B["low_max"]:
        why = "weak signs of local editing"
    else:
        why = "no edited area"
    return Signal(NAME, r.integrity, conf, f"Localizer ({loc.name}) found {why} "
                  f"(integrity {r.integrity:.2f}).", ev)
