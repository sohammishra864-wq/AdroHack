"""Tamper every clean PDF (one method each, round-robin) and make scanned copies, then write
data/docs/manifest.csv.

Methods (PREBUILD.md P1), all change the `total` field:
  incremental       append an incremental update (new content stream + ModDate), original
                    revision still in the file → what pdf_structure's version diff finds
  producer_rewrite  full rewrite by another producer, new ModDate, no history
  digit_paste       rasterize → paste the new number in a different font → image-only PDF
Scans: --scans N copies (random mix of clean + tampered) rasterized with tilt, blur, noise.
Needs Poppler (pdf2image) for digit_paste and scans.
Usage: python scripts/gen/tamper_pdf.py [--scans 30]
"""
import argparse
import csv
import datetime as dt
import json
import random
import re
from pathlib import Path

import numpy as np
import pikepdf
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from invoices import H, money, pdf_date

CLEAN, TAMPERED, SCANS = Path("data/docs/clean"), Path("data/docs/tampered"), Path("data/docs/scans")
METHODS = ("incremental", "producer_rewrite", "digit_paste")
REWRITERS = ("iLovePDF", "Smallpdf.com", "PDF-XChange Editor 9.5", "Nitro Pro 13")
DPI = 200


def new_total(old, rng):
    return money(float(old.replace(",", "")) * rng.uniform(1.3, 2.5))


def tj(text):
    return b"(" + text.encode("latin-1") + b")"


def incremental(src, dst, old, new, when):
    """Append objects + xref section with /Prev. Returns nothing; dst has 2 revisions."""
    raw = Path(src).read_bytes()
    prev = int(re.findall(rb"startxref\s+(\d+)", raw)[-1])
    with pikepdf.open(src) as pdf:
        page, info = pdf.pages[0].obj, pdf.trailer.Info
        content = page.Contents.read_bytes()
        assert content.count(tj(old)) == 1, "field text not unique in content stream"
        content = content.replace(tj(old), tj(new))
        n, (cnum, cgen) = int(pdf.trailer.Size), page.Contents.objgen
        page_txt = page.unparse(resolved=True)
        ref = f"/Contents {cnum} {cgen} R".encode()
        assert ref in page_txt
        page_txt = page_txt.replace(ref, f"/Contents {n} 0 R".encode())
        info_d = pikepdf.Dictionary({k: info[k] for k in info.keys()})
        info_d.ModDate = pdf_date(when)
        objs = {page.objgen: page_txt, info.objgen: info_d.unparse(),
                (n, 0): b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"}
        root, info_ref = pdf.Root.objgen, info.objgen
    body, offsets = bytearray(raw if raw.endswith(b"\n") else raw + b"\n"), {}
    for (num, gen), txt in sorted(objs.items()):
        offsets[num, gen] = len(body)
        body += b"%d %d obj\n" % (num, gen) + txt + b"\nendobj\n"
    xref = len(body)
    body += b"xref\n"
    for (num, gen), off in sorted(offsets.items()):
        body += b"%d 1\n%010d %05d n\r\n" % (num, off, gen)
    body += (b"trailer\n<< /Size %d /Root %d %d R /Info %d %d R /Prev %d >>\nstartxref\n%d\n%%%%EOF\n"
             % (n + 1, *root, *info_ref, prev, xref))
    Path(dst).write_bytes(bytes(body))


def producer_rewrite(src, dst, old, new, when, rng):
    with pikepdf.open(src) as pdf:
        c = pdf.pages[0].obj.Contents
        c.write(c.read_bytes().replace(tj(old), tj(new)))
        pdf.docinfo[pikepdf.Name.Producer] = rng.choice(REWRITERS)
        pdf.docinfo[pikepdf.Name.ModDate] = pdf_date(when)
        pdf.save(dst)


def font(px):
    for f in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            pass
    return ImageFont.load_default(px)


def raster(src):
    from pdf2image import convert_from_path
    return convert_from_path(str(src), dpi=DPI)[0].convert("RGB")


def digit_paste(src, dst, field, new):
    img, k = raster(src), DPI / 72
    x, y, size = field["x"] * k, (H - field["y"]) * k, field["size"] * k
    w = 0.6 * field["size"] * len(field["text"]) * k  # ponytail: width estimate, not metrics
    ImageDraw.Draw(img).rectangle((x - 2, y - size, x + w, y + 0.3 * size), fill="white")
    ImageDraw.Draw(img).text((x, y), new, fill="black", font=font(int(size)), anchor="ls")
    img.save(dst, "PDF", resolution=DPI)


def scan(src, dst, rng):
    img = raster(src).rotate(rng.uniform(-1.5, 1.5), expand=True, fillcolor="white")
    img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 0.9)))
    a = np.asarray(img, np.float32) + np.random.default_rng(rng.randrange(2**31)).normal(0, 6, (img.height, img.width, 1))
    Image.fromarray(np.clip(a * rng.uniform(0.9, 1.0) + 8, 0, 255).astype(np.uint8)).save(
        dst, "PDF", resolution=DPI)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scans", type=int, default=30)
    a = ap.parse_args()
    TAMPERED.mkdir(parents=True, exist_ok=True)
    SCANS.mkdir(parents=True, exist_ok=True)
    rows = []
    clean = sorted(CLEAN.glob("*.pdf"))
    for i, src in enumerate(clean):
        meta = json.loads(src.with_suffix(".json").read_text(encoding="utf-8"))
        doc_type = src.stem.split("_")[0]
        rows.append({"path": src, "label": "clean", "doc_type": doc_type, "tamper": "none",
                     "scan": 0, "src": "", "field": "", "old": "", "new": ""})
        rng, method = random.Random(f"tamper/{src.name}"), METHODS[i % len(METHODS)]
        field = meta["fields"]["total"]
        new = new_total(field["text"], rng)
        when = dt.datetime.fromisoformat(meta["created"]) + dt.timedelta(days=rng.randint(3, 60))
        dst = TAMPERED / f"{src.stem}_{method}.pdf"
        if method == "incremental":
            incremental(src, dst, field["text"], new, when)
        elif method == "producer_rewrite":
            producer_rewrite(src, dst, field["text"], new, when, rng)
        else:
            digit_paste(src, dst, field, new)
        rows.append({"path": dst, "label": "tampered", "doc_type": doc_type, "tamper": method,
                     "scan": 0, "src": src, "field": "total", "old": field["text"], "new": new})
    rng = random.Random("scans")
    for r in rng.sample(rows, min(a.scans, len(rows))):
        dst = SCANS / f"{Path(r['path']).stem}_scan.pdf"
        scan(r["path"], dst, rng)
        rows.append({**r, "path": dst, "scan": 1, "src": r["src"] or r["path"]})
    with open("data/docs/manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows({k: str(v).replace("\\", "/") for k, v in r.items()} for r in rows)
    print(f"data/docs/manifest.csv: {len(rows)} rows")


if __name__ == "__main__":
    main()
