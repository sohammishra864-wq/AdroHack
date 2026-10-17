"""Splices (patch from another seed) and copy-moves (patch from the same seed) on N seeds.

→ data/generated/{splice,copymove}/<attack>/<i>.jpg + <i>_mask.png (white = pasted area).
Usage: python scripts/gen/splice.py [--n 150]
"""
import argparse
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from rows import images, open_rgb, write


def box(W, H, rng):
    w, h = int(W * rng.uniform(0.12, 0.3)), int(H * rng.uniform(0.12, 0.3))
    x, y = rng.randrange(0, W - w), rng.randrange(0, H - h)
    return x, y, x + w, y + h


def paste(dst, patch, at, rng):
    """Paste with a feathered ellipse; returns the hard mask of the pasted area."""
    m = Image.new("L", patch.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, *patch.size), fill=255)
    dst.paste(patch, at, m.filter(ImageFilter.GaussianBlur(rng.uniform(1, 4))))
    full = Image.new("L", dst.size, 0)
    full.paste(m, at)
    return full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seeds", default="data/seeds")
    ap.add_argument("--out", default="data/generated")
    a = ap.parse_args()
    seeds = [p for p in images(a.seeds) if "whatsapp" not in p.parts]
    for attack in ("splice", "copymove"):
        out_dir, rows = Path(a.out, attack, attack), []
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, seed in enumerate(seeds[:a.n]):
            rng = random.Random(f"{attack}/{seed.name}")
            img = open_rgb(seed)
            W, H = img.size
            donor = img if attack == "copymove" else open_rgb(rng.choice(seeds)).resize((W, H))
            src = box(W, H, rng)
            patch = donor.crop(src)
            spot = lambda: (rng.randrange(0, W - patch.width), rng.randrange(0, H - patch.height))
            at = spot()
            if attack == "copymove":  # land clear of the source area
                while abs(at[0] - src[0]) < patch.width and abs(at[1] - src[1]) < patch.height:
                    at = spot()
            mask = paste(img, patch, at, rng)
            path, mpath = out_dir / f"{i:04d}.jpg", out_dir / f"{i:04d}_mask.png"
            img.save(path, quality=95)
            mask.save(mpath)
            rows.append({"path": path, "label": "fake", "family": attack, "attack": attack,
                         "quality": "orig", "seed_path": seed, "mask_path": mpath})
        write(out_dir, rows)


if __name__ == "__main__":
    main()
