"""Deterministic composite scorer. Weights in configs/weights.yaml, bands in thresholds.yaml.

lane score  = Σ w·c·s / Σ w·c   over applicable, non-abstained signals in that lane
overall     = 0.5·max(lanes) + 0.5·mean(lanes) + claim_bonus,  clipped to [0, 1]
claim_bonus = Σ w·c·s           over the three claim-level checks

Waterfall: overall is rewritten exactly as 0.5 + Σ contributions, where a signal in lane L
contributes coeff_L · w·c·(s − 0.5) / Σ w·c and coeff_L = 0.5·[L is the max lane] + 0.5/n.
Because Σ coeff_L = 1, the entries (baseline 0.5 plus contributions) sum to the unclipped
overall, and an "authentic" vote shows up as a negative bar.

Calibration: if configs/calibration.yaml exists (written by `scripts/eval.py --calibrate` on
the calib split only), each listed signal's score s is replaced by sigmoid(a·s + b) before
the formula above. Cards still show the raw score; the waterfall shows calibrated effects.

No conditional gates. The quality gate only caps fast-tier confidence and may force UNCERTAIN.
"""
from __future__ import annotations

import math

from .. import config
from ..contracts import ClaimScore, Region, Signal

LANES = ("image", "document", "identity")


def _usable(s: Signal) -> bool:
    return s.applicable and not s.abstained and s.score is not None


def calibration() -> dict:
    """{signal: {a, b}}; empty until eval.py --calibrate has run."""
    return config.cfg("calibration") if (config.ROOT / "configs" / "calibration.yaml").exists() else {}


def calibrated(name: str, score: float, cal: dict) -> float:
    c = cal.get(name)
    return score if c is None else 1 / (1 + math.exp(-(c["a"] * score + c["b"])))


def _lane_of(name: str, weights: dict) -> str | None:
    return next((L for L in (*LANES, "claim") if name in weights.get(L, {})), None)


def score_claim(signals: list[Signal], quality_flag: bool = False,
                regions: list[Region] | None = None, pending_deep: bool = False) -> ClaimScore:
    W, T, cal = config.cfg("weights"), config.cfg("thresholds"), calibration()
    cap = T["quality_gate"]["confidence_cap_when_flagged"]

    lanes: dict[str, list[tuple[str, float, float]]] = {}
    claim: list[tuple[str, float, float]] = []
    for s in signals:
        lane = _lane_of(s.name, W)
        if lane is None or not _usable(s):
            continue
        c = min(s.confidence, cap) if quality_flag and s.tier == "fast" else s.confidence
        wc = W[lane][s.name] * c
        if wc > 0:
            (claim if lane == "claim" else lanes.setdefault(lane, [])).append(
                (s.name, wc, calibrated(s.name, s.score, cal)))

    lane_score = {L: sum(wc * sc for _, wc, sc in xs) / sum(wc for _, wc, _ in xs)
                  for L, xs in lanes.items()}

    contrib: list[tuple[str, float]] = []
    raw = 0.0
    if lane_score:
        top, n = max(lane_score, key=lane_score.get), len(lane_score)
        for L, xs in lanes.items():
            coeff, tot = 0.5 * (L == top) + 0.5 / n, sum(wc for _, wc, _ in xs)
            contrib += [(name, coeff * wc * (sc - 0.5) / tot) for name, wc, sc in xs]
        raw = 0.5 * lane_score[top] + 0.5 * sum(lane_score.values()) / n
    contrib += [(name, wc * sc) for name, wc, sc in claim]
    raw += sum(wc * sc for _, wc, sc in claim)
    overall = min(1.0, max(0.0, raw))

    waterfall = [("baseline", 0.5 if lane_score else 0.0)]
    waterfall += sorted(contrib, key=lambda kv: -abs(kv[1]))

    B = T["bands"]
    strong = any(_usable(s) and s.name in T["abstain"]["strong_evidence_signals"]
                 and s.score >= B["medium_max"] for s in signals)
    if not lane_score or (quality_flag and not strong):
        band = "UNCERTAIN"
    elif overall < B["low_max"]:
        band = "LOW"
    elif overall < B["medium_max"]:
        band = "MEDIUM"
    else:
        band = "HIGH"

    return ClaimScore(lane_score.get("image"), lane_score.get("document"),
                      lane_score.get("identity"), overall, band, waterfall,
                      regions or [], signals, pending_deep)
