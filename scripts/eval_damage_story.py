"""Measure the damage-vs-story check on real damage photos (data/seeds) → reports/damage_story.md.

  1. what CLIP zero-shot sees: expected severity + front/rear confidence over the seeds
  2. LEGIT stories (vague, moderate 30 km/h, unspecified location): how many get flagged
     (false alarms: the number that matters most)
  3. contradiction stories: "parked, light scratch" and "70 km/h, totalled" on the same photos,
     which shows how often a real contradiction would be caught
Usage: python scripts/eval_damage_story.py [--n 200]
"""
import argparse
import random
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from claimshield.preprocess import prepare  # noqa: E402
from claimshield.signals import clip_probe, damage_story as ds  # noqa: E402

STORIES = {"legit: vague": "My car was damaged in an accident on the way to work.",
           "legit: moderate 30 km/h": "Another car hit mine at about 30 km/h at a junction.",
           "legit: dent, no location": "Someone dented my car in a car park and drove off.",
           "contradiction: parked scratch": "My car was parked and someone left a light scratch.",
           "contradiction: 70 km/h totalled": "I was hit at 70 km/h and the car was totalled."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--out", default=str(ROOT / "reports" / "damage_story.md"))
    a = ap.parse_args()
    seeds = sorted((ROOT / "data" / "seeds").glob("car_*.jpg"))
    seeds = random.Random(0).sample(seeds, min(a.n, len(seeds)))
    reads = []
    for p in seeds:
        prep = prepare(str(p))
        reads.append(ds.read_photo(clip_probe.features(prep)))
    exp = np.array([float(np.dot(s, np.arange(4))) for s, _ in reads])
    front = np.array([float(l[0]) for _, l in reads])
    lines = ["# Damage vs story check", "", f"{len(seeds)} real damage photos from data/seeds (VehiDE).", "",
             "## What CLIP zero-shot sees", "",
             f"Expected severity (0 none … 3 severe): median {np.median(exp):.2f}, "
             f"p5 {np.percentile(exp, 5):.2f}, p95 {np.percentile(exp, 95):.2f}.",
             f"Severity class counts: " + ", ".join(f"{ds.SEVERITY[k]} {int((np.rint(exp) == k).sum())}" for k in range(4)) + ".",
             f"Front vs rear: confident front (≥ {ds.T['loc_seen']}) {int((front >= ds.T['loc_seen']).sum())}, "
             f"confident rear {int((1 - front >= ds.T['loc_seen']).sum())}, unsure {int(((front < ds.T['loc_seen']) & (1 - front < ds.T['loc_seen'])).sum())}.",
             "", "## Flag rate by story (same photos)", "", "| story | flagged | rate |", "|---|---|---|"]
    for name, story in STORIES.items():
        loc, sev = ds.story_claims(story)
        flagged = 0
        for r in reads:
            if not (loc in (None, "side") and sev is None):
                probs, _ = ds.judge(loc, sev, [r])
                flagged += bool(probs)
        lines.append(f"| {name} | {flagged}/{len(reads)} | {flagged / len(reads):.1%} |")
    lines += ["", "Legit rows are false alarms (want ≈ 0). Contradiction rows are not ground truth (some",
              "seeds really are light scratches or wrecks); they show the check reacts when the story",
              "and the photo disagree."]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
