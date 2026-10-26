"""Regions stage 1: reliability-masked localizer heatmap → connected components → boxes,
each with a reason naming which fast signals fired inside it. A box backed by a single
weak signal is not shown. Stage 2 (deep tier) re-scores these boxes with the AE patch map.
"""
from __future__ import annotations

from dataclasses import replace

import cv2
import numpy as np

from . import config
from .contracts import Region, Signal

STRONG = 0.8  # a lone localizer box is shown only if it is at least this hot


def _where(cx: float, cy: float, W: int, H: int) -> str:
    row = ("top", "middle", "bottom")[min(2, int(3 * cy / H))]
    col = ("left", "centre", "right")[min(2, int(3 * cx / W))]
    return "centre" if (row, col) == ("middle", "centre") else f"{row}-{col}"


def _overlaps(a, b) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def stage1(signals: list[Signal], size: tuple[int, int]) -> list[Region]:
    by = {s.name: s for s in signals}
    loc = by.get("localizer")
    if loc is None or loc.score is None or "heatmap" not in loc.evidence:
        return []
    T = config.cfg("thresholds")
    heat, rel = loc.evidence["heatmap"], loc.evidence.get("reliability")
    mask = heat >= 0.5
    if rel is not None:
        mask &= rel >= T["localizer"]["reliability_min"]

    W, H = size
    noise = None
    nr = by.get("noise_residual")
    if nr is not None and "block_z" in nr.evidence:
        b, z = nr.evidence["block_px"], nr.evidence["block_z"]
        noise = np.zeros((H, W), bool)
        up = np.kron(np.abs(z) > T["noise_residual"]["z_outlier"], np.ones((b, b), bool))
        noise[:up.shape[0], :up.shape[1]] = up
    cm = by.get("copy_move")
    cm_boxes = cm.evidence.get("boxes", []) if cm is not None else []

    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    found = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        frac = area / (W * H)
        if frac < T["localizer"]["region_min_area_frac"]:
            continue
        comp = lab == i
        fired = {"localizer": round(float(heat[comp].mean()), 2)}
        if noise is not None and noise[comp].mean() > 0.3:
            fired["noise_residual"] = round(float(noise[comp].mean()), 2)
        box = (int(x), int(y), int(x + w), int(y + h))
        if any(_overlaps(box, b) for b in cm_boxes):
            fired["copy_move"] = 1.0
        if len(fired) < T["regions"]["min_signals_to_show"] and fired["localizer"] < STRONG:
            continue
        found.append((frac, box, fired, _where(*cents[i], W, H)))

    regions = []
    for k, (frac, box, fired, where) in enumerate(sorted(found, key=lambda f: -f[0])):
        parts = [f"localizer anomaly {fired['localizer']:.2f}"]
        if "noise_residual" in fired:
            parts.append("noise level differs")
        if "copy_move" in fired:
            parts.append("matches another area of the photo")
        verdict = ("copy-move" if "copy_move" in fired else
                   "inpainting or splicing" if "noise_residual" in fired else "a local edit")
        reason = (f"Region {chr(65 + k)} ({where}, {frac:.0%}): {', '.join(parts)} "
                  f"→ consistent with {verdict}.")
        regions.append(Region(box, float(frac), fired, reason, stage=1))
    return regions


def stage2(regions: list[Region], ae: Signal) -> list[Region]:
    """Boxes where AE reconstruction error is unusually low gain the AE vote and stage=2.
    ponytail: re-scores stage-1 boxes only; AE-only boxes are not added (ARCHITECTURE "may")."""
    pm = ae.evidence.get("patch_map") if ae.score is not None else None
    if pm is None:
        return regions
    out = []
    for r in regions:
        x0, y0, x1, y1 = r.box
        v = round(float(pm[y0:y1, x0:x1].mean()), 2)
        if v >= 0.5:
            r = replace(r, signals={**r.signals, "ae_reconstruction": v}, stage=2,
                        reason=r.reason.replace(" → ", ", reconstruction error unusually low → ", 1))
        out.append(r)
    return out
