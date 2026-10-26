"""Image lane orchestration: preprocess → fast-tier checks in parallel → cards → score.

Cards are emitted in configs/runtime.yaml `card_order` on the calling thread, so a
Streamlit callback can write to the page directly. The deep tier (AE reconstruction) starts
at the same time on its own executor and never blocks the fast cards: score_image returns
with pending_deep=True and finish() folds the AE signal in once it lands.
"""
from __future__ import annotations

import tempfile
import time
from datetime import datetime
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, replace

from . import config, llm
from .claim import consistency
from .contracts import ClaimScore, Signal
from .narrative import template
from .preprocess import prepare
from .regions import stage1, stage2
from .scoring.composite import score_claim
from .signals import ae_reconstruction, clip_probe, cross_claim, damage_story, family_map, localizer
from .signals.documents import doc_type, fields, medical_billing, ocr, pdf_structure
from .signals.identity import face_match
from .signals.forensics import c2pa, copy_move, exif, jpeg_qtables, noise_residual

# card group → checks, emitted in runtime.yaml card_order.
FAST = {
    "forensics": [c2pa.run, exif.run, jpeg_qtables.run, copy_move.run, noise_residual.run],
    "clip_probe": [clip_probe.run, family_map.run],
    "localizer": [localizer.run],
}

_pool = ThreadPoolExecutor(max_workers=config.cfg("runtime")["fast_tier_workers"])
_deep_pool = ThreadPoolExecutor(max_workers=1)  # one AE job at a time; never shares the fast pool


@dataclass
class ImageResult:
    claim: ClaimScore
    sha256: str
    quality_reasons: list[str]
    t_first: float | None
    t_fast: float
    t_deep: float | None = None   # set by finish() when the deep tier lands
    deep: Future | None = None    # pending (Signal, landed_at) AE job; None when done/disabled
    quality_flag: bool = False
    t0: float = 0.0
    rgb: object = None            # the preprocessed photo, for display after uploads are wiped


def _safe(fn, *args) -> Signal:
    try:
        return fn(*args)
    except Exception as e:  # one broken check must not take the demo down
        name = fn.__module__.rsplit(".", 1)[-1]
        return Signal(name, None, 0.0, f"Check could not run ({type(e).__name__}); "
                      "left out of the score.", {"error": str(e)}, abstained=True)


def score_image(path: str, on_card=None, wait_deep: bool = False) -> ImageResult:
    t0 = time.perf_counter()
    prep = prepare(path)
    R = config.cfg("runtime")
    deep = _deep_pool.submit(lambda: (_safe(ae_reconstruction.run, prep), time.perf_counter())
                             ) if R["deep_tier_enabled"] else None
    order = R["card_order"]
    futures = [_pool.submit(_safe, fn, prep) for g in order for fn in FAST.get(g, [])]

    signals, t_first = [], None
    for f in futures:
        s = f.result()
        signals.append(s)
        t_first = t_first if t_first is not None else time.perf_counter() - t0
        if on_card:
            on_card(s)

    claim = score_claim(signals, quality_flag=prep.quality_flag,
                        regions=stage1(signals, prep.rgb.size), pending_deep=deep is not None)
    res = ImageResult(claim, prep.sha256, prep.quality_reasons, t_first,
                      time.perf_counter() - t0, deep=deep, quality_flag=prep.quality_flag, t0=t0,
                      rgb=prep.rgb)
    return finish(res) if wait_deep else res


def finish(res: ImageResult) -> ImageResult:
    """Block until the deep tier lands, then re-score (waterfall recomputed, regions stage 2)."""
    if res.deep is None:
        return res
    ae, landed = res.deep.result()
    c = res.claim
    claim = score_claim(c.signals + [ae], quality_flag=res.quality_flag,
                        regions=stage2(c.regions, ae))
    return replace(res, claim=claim, t_deep=landed - res.t0, deep=None)


# D3: fast-tier checks that make sense on a page image. No copy_move (fires on repeated
# glyphs), no CLIP probe (trained on photos).
SCAN_CHECKS = [jpeg_qtables.run, noise_residual.run, localizer.run]


@dataclass
class DocResult:
    claim: ClaimScore
    sha256: str
    doc_type: str
    text: str
    from_ocr: bool
    page: object | None   # first page image (scans / image-only PDFs), for the UI
    t_total: float


def _page_image(path: str):
    from PIL import Image, ImageOps

    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).convert("RGB")


def score_document(path: str, on_card=None) -> DocResult:
    """Document lane: PDF structure → text layer or OCR → doc type → field checks; scans
    and image-only PDFs also get the D3 page checks. Sequential: no latency spec here."""
    import hashlib

    t0 = time.perf_counter()
    data = open(path, "rb").read()
    signals: list[Signal] = []

    def emit(s: Signal, tier: str = "doc"):
        s.tier = tier
        signals.append(s)
        if on_card:
            on_card(s)

    text, pages = "", []
    if data[:5] == b"%PDF-":
        try:
            structure, text, _ = pdf_structure.run(data)
        except Exception as e:
            structure = [Signal("pdf_incremental_update", None, 0.0, f"PDF could not be parsed "
                                f"({type(e).__name__}); left out of the score.", {"error": str(e)},
                                abstained=True)]
        for s in structure:
            emit(s)
    scanned = data[:5] != b"%PDF-" or len(text.strip()) < 20
    try:
        pages = ([_page_image(path)] if data[:5] != b"%PDF-" else ocr.render(data)) if scanned else []
        ws = [w for i, p in enumerate(pages) for w in ocr.words(p, i)]
    except Exception as e:  # Tesseract / Poppler missing or unreadable file
        emit(Signal(ocr.NAME, None, 0.0, f"OCR could not run ({type(e).__name__}); left out "
                    "of the score.", {"error": str(e)}, abstained=True))
        ws = None
    if ws is not None and scanned:
        emit(_safe(ocr.run, ws))
        text = ocr.text_of(ws)
    elif not scanned:
        emit(Signal(ocr.NAME, None, 0.0, "Not applicable: the PDF has a text layer, so "
                    "nothing needed OCR.", applicable=False))

    kind = doc_type.classify(text)
    for s in fields.run(text, kind, from_ocr=scanned):
        emit(s)
    emit(_safe(medical_billing.run, text, kind))

    quality_flag = False
    if pages:
        with tempfile.TemporaryDirectory() as d:
            p = f"{d}/page.png"
            pages[0].save(p)
            prep = prepare(p if data[:5] == b"%PDF-" else path)
            quality_flag = prep.quality_flag
            for fn in SCAN_CHECKS:
                emit(_safe(fn, prep), tier="fast")

    claim = score_claim(signals, quality_flag=quality_flag)
    return DocResult(claim, hashlib.sha256(data).hexdigest(), kind, text, scanned,
                     pages[0] if pages else None, time.perf_counter() - t0)


def score_identity(id_path: str, selfie_path: str, on_card=None) -> tuple[list[Signal], str]:
    """→ ([face_match, selfie_synthetic], text read from the ID for the name check)."""
    sigs = [_safe(face_match.run, prepare(id_path).rgb, prepare(selfie_path).rgb)]
    # ponytail: the selfie's deep AE job also starts and is simply not waited for.
    sel = score_image(selfie_path).claim.image_score
    B = config.cfg("thresholds")["bands"]
    sigs.append(Signal("selfie_synthetic", None, 0.0, "Selfie checks could not run; left out "
                       "of the score.", abstained=True) if sel is None else
                Signal("selfie_synthetic", sel, 0.6, "The selfie's own photo checks score "
                       f"{sel:.2f} ({'looks generated or edited' if sel >= B['medium_max'] else 'no clear sign of generation' if sel < B['low_max'] else 'inconclusive'}).",
                       {"image_score": sel}))
    for s in sigs:
        s.tier = "identity"
        if on_card:
            on_card(s)
    try:
        id_text = ocr.text_of(ocr.words(_page_image(id_path)))
    except Exception:  # no Tesseract → name check becomes not applicable
        id_text = ""
    return sigs, id_text


@dataclass
class CaseResult:
    claim: ClaimScore
    images: list[ImageResult]
    documents: list[DocResult]
    narrative: str      # template text with [PLACEHOLDERS]; safe to send to the LLM
    pii: dict           # placeholder → real value; never leaves this process


def _exif(res: ImageResult) -> dict:
    return next((s.evidence for s in res.claim.signals if s.name == "exif"), {})


def score_case(photos: list[str], docs: list[str], id_path: str | None = None,
               selfie_path: str | None = None, on_card=None, case_id: str | None = None,
               story: str | None = None) -> CaseResult:
    """All lanes + the claim-level checks → one ClaimScore and a template narrative.
    With a case_id the claim is also linked to, and stored in, the cross-claim memory."""
    images = [score_image(p, on_card) for p in photos]
    documents = [score_document(p, on_card) for p in docs]
    identity, id_text = score_identity(id_path, selfie_path, on_card) if id_path and selfie_path         else ([], "")
    images = [finish(r) for r in images]  # deep tier had the doc + identity time to land
    return combine(images, documents, identity, id_text, on_card, case_id, remember=bool(case_id),
                   story=story)


def combine(images: list[ImageResult], documents: list[DocResult], identity: list[Signal],
            id_text: str = "", on_card=None, case_id: str | None = None,
            remember: bool = False, story: str | None = None) -> CaseResult:
    """Claim-level checks + one score over already-scored lanes. Images may still have a
    pending deep tier (pending_deep is then set on the result). remember=True only on the
    FINAL combine of a case, so the provisional pass never stores it."""
    shots = [datetime.fromisoformat(e["datetime_original"]) for e in map(_exif, images)
             if e.get("datetime_original")]
    cameras = [f"{e.get('make', '')} {e.get('model', '')}".strip() for e in map(_exif, images)]
    inv_dates = [d for d in (fields.invoice_date(r.text) for r in documents if r.doc_type == "invoice") if d]
    doc_names = [n for n in (fields.person_name(r.text) for r in documents) if n]
    id_name = fields.person_name(id_text) if id_text else None
    checks = [consistency.invoice_before_photo(inv_dates, shots),
              consistency.camera_model_mismatch(cameras),
              _safe(consistency.name_mismatch, id_name, doc_names),
              _safe(cross_claim.for_case, case_id, images, documents, id_text, remember),
              _safe(damage_story.run, story, images)]
    for s in checks:
        s.tier = "claim"
        if on_card:
            on_card(s)

    signals = [s for r in (*images, *documents) for s in r.claim.signals] + identity + checks
    # the quality gate forces UNCERTAIN only when EVERY photo is degraded
    degraded = bool(images) and all(r.quality_flag for r in images)
    claim = score_claim(signals, quality_flag=degraded,
                        regions=[g for r in images for g in r.claim.regions],
                        pending_deep=any(r.deep is not None for r in images))
    text, pii = template.build(claim, [n for n in (id_name, *doc_names) if n])
    return CaseResult(claim, images, documents, text, pii)


def warm() -> list[str]:
    """Load every model (fast tier + AE) up front (`make demo`). Returns problems, never raises:
    a missing model shows up as a grey card instead of blocking the app."""
    problems = []
    for mod in (clip_probe, family_map, localizer, ae_reconstruction, face_match, llm):
        try:
            mod.warm()
        except Exception as e:
            problems.append(f"{mod.__name__.rsplit('.', 1)[-1]}: {e}")
    return problems
