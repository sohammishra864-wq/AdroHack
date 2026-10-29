"""Offline arena: attack N seed photos with each method, re-score before/after →
reports/arena.csv. Each method runs on its own (no fallback) so every column is honest.
The first successful inpaint per method is copied to the pre-generated dir, which is the
live chain's last resort.

Usage: python -m claimshield.arena.run [--seeds data/seeds] [--n 20] [--methods nova,local_sd15,recompress]
"""
from __future__ import annotations

import argparse
import csv
import tempfile
from pathlib import Path

from .. import config
from ..pipeline import score_image
from . import attacks

EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}


def attack(method: str, path: Path, prompt: str) -> attacks.Attack:
    if method == "recompress":
        return attacks.recompress_q70(path)
    img = attacks._open(path)
    out = (attacks.inpaint_nova(img, prompt, attacks._cfg()["mask_prompt"]) if method == "nova"
           else attacks.inpaint_local_sd15(img, prompt))
    return attacks.Attack(attacks._jpeg(out, 95), "inpaint", method, "", 0.0)


def row(seed: Path, method: str, before, after) -> dict:
    r = {"seed": seed.name, "method": method,
         "overall_before": round(before.claim.overall, 4), "band_before": before.claim.band,
         "overall_after": round(after.claim.overall, 4), "band_after": after.claim.band}
    r.update({f"after_{s.name}": "" if s.score is None else round(s.score, 4)
              for s in after.claim.signals})
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="data/seeds")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--methods", default="nova,local_sd15,recompress")
    ap.add_argument("--out", default="reports/arena.csv")
    a = ap.parse_args()

    seeds = sorted(p for p in (config.ROOT / a.seeds).glob("*") if p.suffix.lower() in EXTS)[:a.n]
    pre = config.ROOT / attacks._cfg()["pregenerated_dir"]
    pre.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for seed in seeds:
            before = score_image(str(seed), wait_deep=True)
            for m in a.methods.split(","):
                try:
                    atk = attack(m, seed, attacks._cfg()["prompt"])
                except Exception as e:
                    print(f"{seed.name} {m}: {type(e).__name__}: {e}")
                    continue
                p = Path(d) / f"{seed.stem}_{m}.jpg"
                p.write_bytes(atk.data)
                if atk.kind == "inpaint" and not any(pre.glob(f"inpaint_{m}*.jpg")):
                    (pre / f"inpaint_{m}_{seed.stem}.jpg").write_bytes(atk.data)
                rows.append(row(seed, m, before, score_image(str(p), wait_deep=True)))
            print(f"{seed.name}: done", flush=True)
    cols = sorted({k for r in rows for k in r}, key=lambda k: (k.startswith("after_"), k))
    out = config.ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
