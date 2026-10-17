"""Damage-vs-story demo cases → data/cases/s1_mismatch, s2_legit (needs the CLIP model).

Picks the two seed photos CLIP rates as the lightest damage, then:
  s1_mismatch  "hit at 70 km/h, car totalled"         → damage_story fires (photo: a scratch)
  s2_legit     "scratched while parked" (other photo)  → consistent, stays quiet
Also clears the cross-claim memory (--keep-memory to skip).
Usage: python scripts/gen/story_cases.py
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from claimshield import memory  # noqa: E402
from claimshield.preprocess import prepare  # noqa: E402
from claimshield.signals import clip_probe, damage_story as ds  # noqa: E402

CASES = ROOT / "data" / "cases"
STORIES = [("s1_mismatch", "Story 1: totalled at 70 km/h?",
            "I was hit at 70 km/h on the highway and the car was totalled."),
           ("s2_legit", "Story 2 (legit): scratched while parked",
            "My car was parked outside the office and someone left a light scratch on it.")]


def lightest(n: int = 2, pool: int = 120) -> list[Path]:
    seeds = sorted((ROOT / "data" / "seeds").glob("car_*.jpg"))[:pool]
    sev = [float(np.dot(ds.read_photo(clip_probe.features(prepare(str(p))))[0], np.arange(4))) for p in seeds]
    return [seeds[i] for i in np.argsort(sev)[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-memory", action="store_true")
    a = ap.parse_args()
    for (name, title, story), photo in zip(STORIES, lightest()):
        d = CASES / name
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        shutil.copy(photo, d / "photo.jpg")
        (d / "case.json").write_text(json.dumps({"title": title, "description": story}), encoding="utf-8")
        print(f"wrote data/cases/{name}  ({photo.name})")
    if not a.keep_memory:
        print(f"cross-claim memory cleared ({memory.reset()} rows)")


if __name__ == "__main__":
    main()
