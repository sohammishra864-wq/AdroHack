"""Cross-claim check (fraud-ring memory): pull the reusable entities out of a scored claim
(photo pHash, VIN, vendor letterhead, claimant name), link them to earlier claims through
memory.py, and score the strongest link with the fixed RULES table below.

Scored as a claim-level bonus (weights.yaml claim.cross_claim): no link adds nothing, a reused
photo adds w·c. The same repair shop on its own is shown but scores 0, because honest
customers share shops."""
from __future__ import annotations

import re
from datetime import datetime

import numpy as np
from PIL import Image
from scipy.fft import dct

from .. import memory
from ..contracts import Signal
from .documents import fields

NAME = "cross_claim"
CONFIDENCE = 0.9
# (kinds ALL shared with one earlier case, score); first match wins, nothing matched → 0.
# Legit repeats must stay low: the same patient back at the same hospital on another date (a
# follow-up) is only 0.3; the SAME stay (patient + hospital + admission date) claimed twice is 1.0.
RULES = [({"photo"}, 1.0), ({"stay"}, 1.0),
         ({"vin", "vendor"}, 0.9), ({"vin", "claimant"}, 0.9),
         ({"vin"}, 0.6),
         ({"vendor", "claimant"}, 0.3),
         ({"claimant"}, 0.3)]
WHAT = {"photo": "the same photo (or a resized / recompressed copy)", "vin": "the same VIN",
        "vendor": "the same repair shop / hospital ({})", "claimant": "the same claimant name",
        "stay": "the same hospital stay (same patient, hospital and admission date)"}


def phash(rgb: Image.Image) -> str:
    """64-bit DCT perceptual hash (the imagehash.phash recipe): 32×32 grey → 2-D DCT →
    top-left 8×8 low frequencies → bit = above their median. Survives resize + recompression."""
    g = np.asarray(rgb.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    low = dct(dct(g, axis=0, norm="ortho"), axis=1, norm="ortho")[:8, :8]
    return f"{int(''.join('1' if b else '0' for b in (low > np.median(low)).flat), 2):016x}"


VIN_LABEL = re.compile(r"\b(?:VIN|chassis(?:\s*(?:no|number))?)\b\.?\s*[:#\-]?\s*([A-Z0-9][A-Z0-9 \-]{15,22})", re.I)
VIN_BARE = re.compile(r"\b[A-Z0-9]{17}\b")
_OCR_FIX = str.maketrans("OIQ", "010")   # VINs never use O, I or Q; OCR often reads 0/1 as them


def _vin(s: str) -> str | None:
    v = re.sub(r"[\s\-]", "", s.upper()).translate(_OCR_FIX)[:17]
    ok = re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", v) and re.search(r"[A-Z]", v) and re.search(r"\d", v)
    return v if ok else None


def vins(text: str) -> list[str]:
    """Labelled VIN / chassis numbers first, then any bare 17-character VIN-shaped token."""
    found = [_vin(m.group(1)) for m in VIN_LABEL.finditer(text)] + [_vin(m.group(0)) for m in VIN_BARE.finditer(text)]
    return sorted({v for v in found if v})


VENDOR_LABEL = re.compile(r"^\s*(?:vendor|garage|workshop|repairer|repair shop|service cent(?:re|er)|"
                          r"hospital|clinic|billed by)\s*[:\-]\s*(.+)$", re.I)
TITLE_WORDS = re.compile(r"\b(?:tax\s+invoice|invoice|receipt|estimate|discharge\s+summary)\b", re.I)


def vendor(text: str, doc_type: str) -> str | None:
    """Repair shop / hospital: a labelled line, else the letterhead (first line) of an
    invoice or medical document with the title word ("INVOICE") removed."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        m = VENDOR_LABEL.match(ln)
        if m and re.search(r"[A-Za-z]{3}", m.group(1)):
            return m.group(1).strip()
    if doc_type not in ("invoice", "medical") or not lines:
        return None
    v = " ".join(TITLE_WORDS.sub(" ", lines[0]).split())
    return v if re.search(r"[A-Za-z]{3}", v) and len(v) <= 60 else None


def entities(images, documents, id_text: str = "") -> dict[str, list[str]]:
    """Scored ImageResults / DocResults (pipeline.py) → {kind: values} for memory.py."""
    texts = [d.text for d in documents if d.text]
    return {"photo": [phash(r.rgb) for r in images if r.rgb is not None],
            "vin": sorted({v for t in texts for v in vins(t)}),
            "vendor": sorted({v for d in documents if (v := vendor(d.text or "", d.doc_type))}),
            "claimant": sorted({n for t in (*texts, id_text) if t and (n := fields.person_name(t))}),
            "stay": sorted({s for d in documents if (s := stay(d.text or "", d.doc_type))})}


def stay(text: str, doc_type: str) -> str | None:
    """Medical stay key: hospital | patient | admission date (one stay = one claim)."""
    if doc_type != "medical":
        return None
    adm = next((d for k, d in fields.dated(text.splitlines()).items() if k.startswith("admi")), None)
    hosp, who = vendor(text, doc_type), fields.person_name(text)
    return f"{hosp}|{who}|{adm.isoformat()}" if adm and hosp and who else None


def strongest(links: list[dict]) -> tuple[float, str | None, set]:
    """→ (score, earlier case_id, kinds it shares) for the best-scoring earlier case."""
    shared: dict[str, set] = {}
    for l in links:
        shared.setdefault(l["case_id"], set()).add(l["kind"])
    best = (0.0, None, set())
    for case, kinds in shared.items():
        s = next((sc for need, sc in RULES if need <= kinds), 0.0)
        if s > best[0] or best[1] is None:
            best = (s, case, kinds)
    return best


def run(case_id: str | None, ents: dict[str, list[str]], remember: bool = False,
        path=None, now=None) -> Signal:
    """Link this claim to earlier ones; with remember=True also store it (final combine only).
    The reason never names the claimant or the VIN (it goes into the narrative)."""
    if not case_id or not any(ents.values()):
        return Signal(NAME, None, 0.0, "Not applicable: nothing in this claim (photo, VIN, repair "
                      "shop or name) to compare with earlier claims.", applicable=False, tier="claim")
    found = memory.links(case_id, ents, path=path, now=now)
    if remember:
        memory.remember(case_id, ents, path=path, now=now)
    ev = {"links": found, "entities": {k: len(v) for k, v in ents.items()}}
    if not found:
        return Signal(NAME, 0.0, CONFIDENCE, f"No earlier claim in the last {memory.WINDOW_DAYS} "
                      "days shares this claim's photos, VIN, repair shop or claimant.", ev, tier="claim")
    s, case, kinds = strongest(found)
    others = len({l["case_id"] for l in found}) - 1
    shop = next((l["value"] for l in found if l["case_id"] == case and l["kind"] == "vendor"), "")
    shown = kinds - {"vendor", "claimant"} if "stay" in kinds else kinds   # the stay already says both
    what = [WHAT[k].format(shop) for k in ("stay", "photo", "vin", "vendor", "claimant") if k in shown]
    when = datetime.fromisoformat(min(l["ts"] for l in found if l["case_id"] == case)).astimezone().date()
    reason = (f"Shares {' and '.join(what)} with earlier claim {case} ({when})"
              + (f", plus links to {others} other claim(s)" if others else "")
              + ("; a shared shop alone is common, so it is not scored." if s == 0 else "."))
    return Signal(NAME, s, CONFIDENCE, reason, ev, tier="claim")


def for_case(case_id: str | None, images, documents, id_text: str = "",
             remember: bool = False) -> Signal:
    """pipeline.combine() entry point: extract + link (+ store)."""
    return run(case_id, entities(images, documents, id_text), remember)
