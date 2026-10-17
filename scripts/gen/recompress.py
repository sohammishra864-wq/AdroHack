"""q90 / q70 / q50 JPEG and a 512 px downscale (dn512) of every quality=orig row except
real-wild → data/generated/recompress/<quality>/<sha1 of source>.jpg. Run after everything else, then
re-run manifest.py. Variants keep label/family/attack/seed/mask and record `src`.
Usage: python scripts/gen/recompress.py
"""
import hashlib
from pathlib import Path

import manifest
from rows import open_rgb, write

VARIANTS = {"q90": 90, "q70": 70, "q50": 50, "dn512": 90}


def main():
    src = [r for r in manifest.load()
           if r.get("quality") == "orig" and not r.get("wild") and "/recompress/" not in r["path"]]
    for q, jq in VARIANTS.items():
        out_dir, rows = Path("data/generated/recompress", q), []
        out_dir.mkdir(parents=True, exist_ok=True)
        for r in src:
            path = out_dir / f"{hashlib.sha1(r['path'].encode()).hexdigest()[:16]}.jpg"
            if not path.exists():
                img = open_rgb(r["path"])
                if q == "dn512":
                    img.thumbnail((512, 512))
                img.save(path, quality=jq)
            rows.append({**r, "path": path, "quality": q, "src": r["path"]})
        write(out_dir, rows)


if __name__ == "__main__":
    main()
