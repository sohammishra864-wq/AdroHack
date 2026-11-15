"""D1: OCR for scans and image-only PDFs. Tesseract --psm 6 with per-word confidence; a
pasted or retouched number often OCRs with a confidence dip against its neighbours.
"""
from __future__ import annotations

import re

from ... import config
from ...contracts import Signal

NAME = "ocr_confidence_dip"
NUMERIC = re.compile(r"\d")


def render(data: bytes):
    """PDF bytes → list of RGB page images (first ocr_max_pages)."""
    from pdf2image import convert_from_bytes

    C = config.cfg("thresholds")["documents"]
    return [p.convert("RGB") for p in
            convert_from_bytes(data, dpi=C["ocr_dpi"], first_page=1, last_page=C["ocr_max_pages"])]


def words(img, page: int = 0) -> list[dict]:
    import pytesseract

    d = pytesseract.image_to_data(img, config="--psm 6", output_type=pytesseract.Output.DICT)
    return [{"text": t, "conf": float(c), "page": page,
             "box": (d["left"][i], d["top"][i], d["left"][i] + d["width"][i], d["top"][i] + d["height"][i])}
            for i, (t, c) in enumerate(zip(d["text"], d["conf"])) if t.strip() and float(c) >= 0]


def text_of(ws: list[dict]) -> str:
    """Rebuild lines from word boxes (same page, overlapping vertical band)."""
    lines: list[list[dict]] = []
    for w in sorted(ws, key=lambda w: (w["page"], w["box"][1], w["box"][0])):
        last = lines[-1][-1] if lines else None
        if last and last["page"] == w["page"] and abs(w["box"][1] - last["box"][1]) < \
                0.6 * (w["box"][3] - w["box"][1]):
            lines[-1].append(w)
        else:
            lines.append([w])
    return "\n".join(" ".join(w["text"] for w in sorted(ln, key=lambda w: w["box"][0])) for ln in lines)


def dips(ws: list[dict]) -> list[dict]:
    below = config.cfg("thresholds")["documents"]["ocr_dip_below"]
    return [w for w in ws if NUMERIC.search(w["text"]) and w["conf"] < below]


def run(ws: list[dict]) -> Signal:
    num = [w for w in ws if NUMERIC.search(w["text"])]
    if not num:
        return Signal(NAME, None, 0.0, "Not applicable: no numbers were read from the page.",
                      {"words": ws}, applicable=False)
    bad = dips(ws)
    ev = {"words": ws, "dips": bad}
    if bad:
        shown = ", ".join(f"\"{w['text']}\" ({w['conf']:.0f})" for w in bad[:3])
        return Signal(NAME, min(0.8, 0.5 + 0.1 * len(bad)), 0.4,
                      f"{len(bad)} of {len(num)} numbers read with unusually low confidence: {shown}.", ev)
    return Signal(NAME, 0.25, 0.3, f"All {len(num)} numbers read cleanly.", ev)
