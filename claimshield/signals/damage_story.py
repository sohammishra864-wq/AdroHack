"""Damage vs story (the honest "physics" check): does the damage visible in the photos fit what
the claimant says happened? The story gives an impact location (front / rear / side) and a
severity (speed in km/h, or words like "parked", "totalled"); CLIP ViT-L/14 zero-shot rates each
photo's damage severity and location.

Built to leave honest claims alone: no story or a vague one → not applicable; it fires only on a
clear contradiction (a severe crash claimed but the photos show at most a scratch, or the reverse;
rear claimed but confidently front damage, or the reverse); side impacts are never judged; with
several photos the BEST-matching one counts. Zero-shot, no trained head → confidence ≤ 0.5.
"""
from __future__ import annotations

import re
from functools import lru_cache

import numpy as np

from .. import config
from ..contracts import Signal
from . import clip_probe

NAME = "damage_story"
CONFIDENCE = 0.5
SEVERITY = ["no visible damage", "a light scratch", "a dent", "severe crash damage"]
SEV_PROMPTS = [["a photo of an undamaged car", "a clean car with no damage"],
               ["a photo of a car with a light scratch on the paint", "a small scrape on a car"],
               ["a photo of a car with a dented panel", "a dent in a car body"],
               ["a photo of a badly crashed car with crumpled metal", "a wrecked, crushed car after a collision"]]
LOCATIONS = ["front", "rear"]
LOC_PROMPTS = [["damage to the front bumper, bonnet and headlights of a car", "a car's damaged front end"],
               ["damage to the rear bumper, boot and tail lights of a car", "a car's damaged rear end"]]
STORY_LOC = {"rear": ("rear-ended", "rear ended", "from behind", "rear bumper", "tail light", "boot", "trunk",
                      "reversed into me", "backed into me"),
             "front": ("head-on", "head on", "front bumper", "bonnet", "hood", "headlight", "hit a wall",
                       "hit a pole", "hit a tree", "the car in front", "ran into"),
             "side": ("t-boned", "sideswiped", "side-swiped", "side door", "driver door", "passenger door")}
MINOR = ("scratch", "scrape", "minor", "parked", "small dent", "low speed", "bumped")
SEVERE = ("totalled", "totaled", "write-off", "written off", "airbag", "rolled over", "high speed", "crushed")
SPEED = re.compile(r"(\d{1,3})\s*(km/?h|kmph|kph|mph)", re.I)
T = {"sev_gap": 1.75, "loc_seen": 0.70, "loc_claimed_max": 0.15}   # set from the seed measurement


def story_claims(text: str) -> tuple[str | None, int | None]:
    """→ (location, severity 1..3) the claimant states; None where the story doesn't say."""
    low = (text or "").lower()
    loc = next((k for k, words in STORY_LOC.items() if any(w in low for w in words)), None)
    m = SPEED.search(low)
    if m:
        kmh = int(m.group(1)) * (1.6 if m.group(2).lower() == "mph" else 1)
        sev = 1 if kmh < 15 else 2 if kmh <= 50 else 3
    else:
        sev = 3 if any(w in low for w in SEVERE) else 1 if any(w in low for w in MINOR) else None
    return loc, sev


@lru_cache(maxsize=1)
def _text():
    import open_clip
    import torch

    m, _ = clip_probe.model()
    tok = open_clip.get_tokenizer(config.cfg("runtime")["clip"]["arch"])

    def enc(groups):
        with torch.inference_mode():
            out = []
            for prompts in groups:
                f = m.encode_text(tok(prompts).to(config.device())).float()
                f = (f / f.norm(dim=-1, keepdim=True)).mean(0)
                out.append((f / f.norm()).cpu().numpy())
        return np.stack(out)
    return enc(SEV_PROMPTS), enc(LOC_PROMPTS)


def _soft(x):
    e = np.exp(100 * (x - x.max()))
    return e / e.sum()


def read_photo(feat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """CLIP features → (severity probs over SEVERITY, location probs over LOCATIONS)."""
    sev, loc = _text()
    return _soft(sev @ feat), _soft(loc @ feat)


def judge(claim_loc, claim_sev, photos) -> tuple[list[str], dict]:
    """photos: [(sev_probs, loc_probs)]. → (problems of the best-matching photo, evidence)."""
    best = None
    for sp, lp in photos:
        e = float(np.dot(sp, np.arange(4)))           # expected severity 0..3
        probs = []
        if claim_sev is not None and abs(claim_sev - e) >= T["sev_gap"]:
            seen = SEVERITY[int(round(e))]
            probs.append(f"the story implies {'a severe crash' if claim_sev == 3 else 'only minor damage'} "
                         f"but the photo looks like {seen}")
        if claim_loc in LOCATIONS:
            other = LOCATIONS[1 - LOCATIONS.index(claim_loc)]
            p_other, p_claim = float(lp[LOCATIONS.index(other)]), float(lp[LOCATIONS.index(claim_loc)])
            if p_other >= T["loc_seen"] and p_claim <= T["loc_claimed_max"]:
                probs.append(f"the story says {claim_loc} impact but the damage looks like the {other}")
        ev = {"expected_severity": round(e, 2), "severity_probs": [round(float(x), 3) for x in sp],
              "location_probs": dict(zip(LOCATIONS, (round(float(x), 3) for x in lp)))}
        if best is None or len(probs) < len(best[0]):
            best = (probs, ev)
    return best


def run(story: str | None, images) -> Signal:
    """story: the claim description; images: scored ImageResults (need .rgb and .sha256)."""
    claim_loc, claim_sev = story_claims(story or "")
    if not story or (claim_loc in (None, "side") and claim_sev is None):
        return Signal(NAME, None, 0.0, "Not applicable: no accident description with an impact "
                      "location or severity to compare with the photos.", applicable=False, tier="claim")
    shots = [r for r in images if getattr(r, "rgb", None) is not None]
    if not shots:
        return Signal(NAME, None, 0.0, "Not applicable: no photo to compare with the description.",
                      applicable=False, tier="claim")
    problems, ev = judge(claim_loc, claim_sev, [read_photo(clip_probe.features(r)) for r in shots])
    ev |= {"story_location": claim_loc, "story_severity": claim_sev, "photos": len(shots)}
    if not problems:
        return Signal(NAME, 0.0, CONFIDENCE, "The visible damage is consistent with the accident "
                      "description.", ev, tier="claim")
    return Signal(NAME, 0.8 if len(problems) > 1 else 0.6, CONFIDENCE,
                  "Damage does not fit the story: " + "; ".join(problems) + ".", ev, tier="claim")
