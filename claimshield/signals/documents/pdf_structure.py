"""D0: PDF structure forensics — the "time machine".

An incremental update appends a new revision after the first %%EOF. Cutting the file at
each earlier %%EOF gives a valid older PDF; diffing its text against the final text gives
the version-diff table. Also: producer / dates metadata, and rare fonts on digits.
Returns three Signals: pdf_incremental_update, pdf_producer_mismatch, pdf_font_anomaly.
"""
from __future__ import annotations

import difflib
import io
import re
from collections import Counter
from datetime import datetime

from ... import config
from ...contracts import Signal

EDITORS = ("ilovepdf", "smallpdf", "pdf-xchange", "nitro", "sejda", "foxit phantom",
           "pdfescape", "pdf candy", "pdffiller", "dochub", "acrobat pro", "pdfelement")


def revisions(data: bytes) -> list[bytes]:
    """Every saved state of the file, oldest first (the last one is the file itself)."""
    ends = [m.end() for m in re.finditer(rb"%%EOF", data)]
    if b"/Linearized" in data[:1024] and len(ends) > 1:
        ends = ends[1:]  # the first %%EOF of a linearized file is not a revision
    return [data[:e] for e in ends[:-1]] + [data]


def text_of(data: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def diff_rows(old: str, new: str, limit: int = 20) -> list[tuple[str, str]]:
    a, b = old.splitlines(), new.splitlines()
    rows = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if op != "equal":
            rows += [(x, y) for x, y in zip(
                a[i1:i2] + [""] * max(0, (j2 - j1) - (i2 - i1)),
                b[j1:j2] + [""] * max(0, (i2 - i1) - (j2 - j1)))]
    return rows[:limit]


def incremental(data: bytes, final_text: str) -> Signal:
    name, revs = "pdf_incremental_update", revisions(data)
    n = len(revs) - 1
    if n == 0:
        return Signal(name, 0.1, 0.5, "Saved once; no later edits are recorded inside the file.",
                      {"revisions": 1})
    try:
        first = text_of(revs[0])
    except Exception as e:  # a damaged earlier revision still proves the file was re-saved
        return Signal(name, 0.6, 0.4, f"Saved {n + 1} times; the earlier version could not "
                      "be read back.", {"revisions": n + 1, "error": str(e)})
    rows = diff_rows(first, final_text)
    ev = {"revisions": n + 1, "diff": rows}
    if rows:
        old, new = rows[0]
        return Signal(name, 0.9, 0.9, f"This PDF was saved {n + 1} times. The first version "
                      f"reads \"{old.strip()}\" where the final reads \"{new.strip()}\".", ev)
    return Signal(name, 0.45, 0.3, f"Saved {n + 1} times but the visible text did not change "
                  "(signatures and form fills also do this).", ev)


def pdf_date(v) -> datetime | None:
    m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?", str(v or ""))
    if not m:
        return None
    y, mo, d, h, mi, s = (int(g) if g else dflt for g, dflt in zip(m.groups(), (0, 1, 1, 0, 0, 0)))
    try:
        return datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None


def producer(info: dict) -> Signal:
    name = "pdf_producer_mismatch"
    prod, creator = str(info.get("/Producer", "")), str(info.get("/Creator", ""))
    made, mod = pdf_date(info.get("/CreationDate")), pdf_date(info.get("/ModDate"))
    days = (mod - made).days if made and mod else None
    ev = {"producer": prod, "creator": creator, "created": made and made.isoformat(),
          "modified": mod and mod.isoformat(), "days_between": days}
    if not (prod or creator or made):
        return Signal(name, None, 0.0, "Not applicable: the file records no producer or dates.",
                      ev, applicable=False)
    editor = any(e in prod.lower() for e in EDITORS)
    late = days is not None and days >= config.cfg("thresholds")["documents"]["mod_after_create_days"]
    if editor and late:
        return Signal(name, 0.8, 0.6, f"Last saved by {prod}, {days} days after it was created"
                      + (f" in {creator}." if creator else "."), ev)
    if editor:
        return Signal(name, 0.65, 0.5, f"Last saved by {prod}, an online PDF editor"
                      + (f"; created in {creator}." if creator else "."), ev)
    if late:
        return Signal(name, 0.55, 0.35, f"Modified {days} days after it was created.", ev)
    return Signal(name, 0.2, 0.4, f"Created and last saved by {prod or creator or 'the same tool'} "
                  "with no later modification date.", ev)


def fonts(chars: list[dict]) -> Signal:
    """Rogue font: a font used by very few characters, most of them digits."""
    name = "pdf_font_anomaly"
    if not chars:
        return Signal(name, None, 0.0, "Not applicable: no text layer (image-only PDF).",
                      applicable=False)
    rare = config.cfg("thresholds")["documents"]["font_rare_frac"]
    count = Counter(c["fontname"] for c in chars)
    rogue = {}
    for f, k in count.items():
        mine = [c["text"] for c in chars if c["fontname"] == f]
        digits = sum(t.isdigit() or t in ".," for t in mine)
        if len(count) > 1 and k / len(chars) < rare and digits / k >= 0.6:
            rogue[f] = "".join(mine)[:40]
    ev = {"fonts": dict(count), "rogue": rogue}
    if rogue:
        f, txt = next(iter(rogue.items()))
        return Signal(name, 0.8, 0.6, f"The characters \"{txt}\" use a font ({f.split('+')[-1]}) "
                      "found nowhere else in the document.", ev)
    return Signal(name, 0.2, 0.3, f"{len(count)} font(s), used consistently.", ev)


def run(data: bytes) -> tuple[list[Signal], str, list[dict]]:
    """→ (three signals, final text layer, chars with fontname/x0/top/page)."""
    import pdfplumber
    import pikepdf

    chars, pages = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for i, p in enumerate(pdf.pages):
            pages.append(p.extract_text() or "")
            chars += [{"text": c["text"], "fontname": c["fontname"], "page": i} for c in p.chars]
    text = "\n".join(pages)
    with pikepdf.open(io.BytesIO(data)) as pdf:
        info = {str(k): str(v) for k, v in pdf.docinfo.items()}
    return [incremental(data, text), producer(info), fonts(chars)], text, chars
