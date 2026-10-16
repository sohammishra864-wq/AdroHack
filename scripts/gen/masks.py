"""One damage mask per seed: data/masks/<seed stem>.png, white = region to edit.

A random blob (union of ellipses) covering 3–15 % of the image, biased to the lower two
thirds where bumpers, doors and floors usually are. Deterministic per seed name.
Usage: python scripts/gen/masks.py [--seeds data/seeds] [--out data/masks]
"""
import argparse
import hashlib
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from rows import images, open_rgb


def blob(W, H, rng):
    # ponytail: geometry only, no segmentation — masks can land on sky/road. Add SAM if the
    # inpaints look implausible in review.
    m = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(m)
    target = rng.uniform(0.03, 0.15) * W * H
    cx, cy = rng.uniform(0.2, 0.8) * W, rng.uniform(0.35, 0.85) * H
    while np.count_nonzero(np.asarray(m)) < target:
        rx, ry = rng.uniform(0.04, 0.12) * W, rng.uniform(0.04, 0.12) * H
        x, y = cx + rng.uniform(-1, 1) * rx, cy + rng.uniform(-1, 1) * ry
        d.ellipse((x - rx, y - ry, x + rx, y + ry), fill=255)
        cx, cy = x, y
    return m


def make(seed_path, out_dir):
    W, H = open_rgb(seed_path).size
    rng = random.Random(hashlib.sha1(Path(seed_path).name.encode()).hexdigest())
    out = Path(out_dir) / f"{Path(seed_path).stem}.png"
    blob(W, H, rng).save(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="data/seeds")
    ap.add_argument("--out", default="data/masks")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    seeds = [p for p in images(a.seeds) if "whatsapp" not in p.parts]
    for p in seeds:
        make(p, a.out)
    print(f"wrote {len(seeds)} masks to {a.out}")


if __name__ == "__main__":
    main()
