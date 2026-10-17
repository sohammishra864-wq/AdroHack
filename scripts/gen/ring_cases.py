"""Fraud-ring demo cases for the cross-claim check → data/cases/r1_first, r2_reuse, r3_vin.

  r1_first  a real seed photo + invoice from shop S with VIN V, claimant A
  r2_reuse  a WhatsApp-style copy of r1's photo (half size, JPEG q50, no EXIF) + an invoice
            from a different shop, claimant B                → linked to r1 by the photo
  r3_vin    a different seed photo + invoice from shop S with VIN V, claimant C
                                                             → linked to r1 by shop + VIN
Score them in that order (r1 → r2 → r3). Also clears the cross-claim memory so every
rehearsal starts clean (--keep-memory to skip).
Usage: python scripts/gen/ring_cases.py [--seeds car_0001.jpg car_0002.jpg]
"""
import argparse
import io
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import invoices  # noqa: E402  (same folder)
from claimshield import memory  # noqa: E402

CASES = ROOT / "data" / "cases"
VIN = "MA3EYD32S00123456"
SHOP, OTHER_SHOP = 0, 3   # VENDORS index: Speedline Auto Repairs / Northgate Glass & Glazing


def whatsapp_copy(src: Path, dst: Path) -> None:
    im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    im = im.resize((im.width // 2, im.height // 2))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=50)          # re-encoded, no EXIF: what a forward looks like
    dst.write_bytes(buf.getvalue())


def write_invoice(dst: Path, i: int, vendor: int, customer: str, vin: str | None) -> None:
    page, producer, created, _ = invoices.invoice(i, random.Random(f"ring/{i}"), vendor, customer, vin)
    invoices.write_pdf(dst, page.items, producer, created)


def build(seed_a: Path, seed_b: Path, out: Path = CASES) -> list[Path]:
    dirs = [out / n for n in ("r1_first", "r2_reuse", "r3_vin")]
    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
    r1, r2, r3 = dirs
    shutil.copy(seed_a, r1 / f"photo{seed_a.suffix.lower()}")
    write_invoice(r1 / "invoice.pdf", 9001, SHOP, "Asha Verma", VIN)
    whatsapp_copy(seed_a, r2 / "photo.jpg")
    write_invoice(r2 / "invoice.pdf", 9002, OTHER_SHOP, "Rahul Nair", None)
    shutil.copy(seed_b, r3 / f"photo{seed_b.suffix.lower()}")
    write_invoice(r3 / "invoice.pdf", 9003, SHOP, "Priya Iyer", VIN)
    for d, title in zip(dirs, ("Ring 1: first claim", "Ring 2: forwarded photo",
                               "Ring 3: same shop and VIN")):
        (d / "case.json").write_text(json.dumps({"title": title}), encoding="utf-8")
    return dirs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs=2, default=["car_0001.jpg", "car_0002.jpg"])
    ap.add_argument("--keep-memory", action="store_true")
    a = ap.parse_args()
    seeds = [ROOT / "data" / "seeds" / s for s in a.seeds]
    missing = [str(s) for s in seeds if not s.exists()]
    if missing:
        sys.exit(f"seed photo not found: {', '.join(missing)}")
    for d in build(*seeds):
        print(f"wrote {d.relative_to(ROOT)}")
    if not a.keep_memory:
        print(f"cross-claim memory cleared ({memory.reset()} rows)")
    print("Score r1_first → r2_reuse → r3_vin in that order.")


if __name__ == "__main__":
    main()
