"""Merge every data/generated/**/_rows.csv plus the hand-collected folders into
data/generated/manifest.csv (columns in README) and assign heldout + split.

Folders (all optional):
  data/seeds/**             real, family=real (data/seeds/whatsapp/** → quality=whatsapp)
  data/wild/**              real, split=wild (FPR only)
  data/wild/faces/**        the ~200 real face crops (eval reports them separately)
  data/gan/**               fake, family=gan, split=eval_only (never trains anything)
  data/manual/<family>/**   fake, e.g. data/manual/firefly, data/manual/midjourney

Split: rows sharing a source seed always land in the same split (hash of the seed), so
test-seen seeds are disjoint from calib and train. Flux → heldout=1, split=test.
Usage: python scripts/gen/manifest.py
"""
import csv
import hashlib
from pathlib import Path

from rows import images

OUT = Path("data/generated/manifest.csv")
COLS = ["path", "label", "family", "attack", "quality", "heldout", "split", "seed_path", "mask_path"]
HELDOUT = {"flux"}
SPLITS = [("train", 0.60), ("calib", 0.15), ("test", 0.25)]


def _p(p):
    return str(p).replace("\\", "/")


def folder_rows():
    rows, seeds = [], Path("data/seeds")
    for p in images(seeds):
        wa = "whatsapp" in p.relative_to(seeds).parts
        orig = seeds / p.name
        rows.append({"path": p, "label": "real", "family": "real", "attack": "none",
                     "quality": "whatsapp" if wa else "orig",
                     "seed_path": orig if wa and orig.exists() else p})
    rows += [{"path": p, "label": "real", "family": "real", "attack": "none", "quality": "orig",
              "wild": 1} for p in images("data/wild")]
    rows += [{"path": p, "label": "fake", "family": "gan", "attack": "t2i", "quality": "orig"}
             for p in images("data/gan")]
    for d in sorted(Path("data/manual").glob("*")) if Path("data/manual").exists() else []:
        rows += [{"path": p, "label": "fake", "family": d.name, "attack": "t2i", "quality": "orig"}
                 for p in images(d)]
    return rows


def load():
    """All rows (generated + folders), without heldout/split."""
    rows = []
    for f in sorted(Path("data/generated").rglob("_rows.csv")):
        rows += list(csv.DictReader(open(f, encoding="utf-8")))
    rows += folder_rows()
    return [{k: _p(v or "") for k, v in r.items()} for r in rows]


def split_of(r):
    if r.get("wild"):
        return "wild"
    if r["family"] == "gan":
        return "eval_only"
    if r["family"] in HELDOUT:
        return "test"
    group = r.get("seed_path") or r.get("src") or r["path"]
    u = int(hashlib.sha1(group.encode()).hexdigest()[:8], 16) / 2**32
    for name, frac in SPLITS:
        if u < frac:
            return name
        u -= frac
    return SPLITS[-1][0]


def main():
    rows = load()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r["heldout"] = int(r["family"] in HELDOUT)
            r["split"] = split_of(r)
            w.writerow({c: r.get(c, "") for c in COLS})
    print(f"{OUT}: {len(rows)} rows")


if __name__ == "__main__":
    main()
