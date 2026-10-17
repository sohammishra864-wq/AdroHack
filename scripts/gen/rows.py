"""Every generator writes <out_dir>/_rows.csv; scripts/gen/manifest.py merges them.

All paths are relative to the repo root (run scripts from there; on the HPC from
$SCRATCH/claimshield, which mirrors the repo layout). `src` is the row a variant was made
from, so the manifest can keep a source and its variants in the same split.
"""
import csv
from pathlib import Path

COLS = ["path", "label", "family", "attack", "quality", "seed_path", "mask_path", "src"]


def write(out_dir, rows):
    out = Path(out_dir) / "_rows.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        for r in rows:
            w.writerow({c: str(r.get(c, "") or "").replace("\\", "/") for c in COLS})
    print(f"{out}: {len(rows)} rows")


def open_rgb(path):
    """EXIF-rotated RGB; HEIC works when pillow-heif is installed."""
    from PIL import Image, ImageOps
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        pass
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def images(d):
    exts = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
    return sorted(p for p in Path(d).rglob("*") if p.suffix.lower() in exts)
