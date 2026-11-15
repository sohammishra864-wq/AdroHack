"""Claim-level checks — EXACTLY three (README). Each scores 1 when it fires and 0 when it
passes, because the scorer adds them as a bonus (w·c·s): a passing check adds nothing.
"""
from __future__ import annotations

from datetime import date, datetime

from ..contracts import Signal

NAME_MIN_SIMILARITY = 85  # RapidFuzz token_sort_ratio


def invoice_before_photo(invoice_dates: list[date], photo_dates: list[datetime]) -> Signal:
    name = "invoice_before_photo"
    if not invoice_dates or not photo_dates:
        return Signal(name, None, 0.0, "Not applicable: needs an invoice date and a photo with "
                      "a capture date.", applicable=False, tier="claim")
    inv, shot = min(invoice_dates), min(photo_dates).date()
    ev = {"invoice_date": inv.isoformat(), "earliest_photo": shot.isoformat()}
    if inv < shot:
        return Signal(name, 1.0, 0.8, f"The repair invoice ({inv:%d %b %Y}) is dated before the "
                      f"earliest damage photo was taken ({shot:%d %b %Y}).", ev, tier="claim")
    return Signal(name, 0.0, 0.8, "The invoice is dated after the damage photos.", ev, tier="claim")


def camera_model_mismatch(cameras: list[str]) -> Signal:
    name = "camera_model_mismatch"
    known = sorted({c for c in cameras if c})
    if len([c for c in cameras if c]) < 2:
        return Signal(name, None, 0.0, "Not applicable: needs two photos with camera metadata.",
                      applicable=False, tier="claim")
    if len(known) > 1:
        return Signal(name, 1.0, 0.6, f"The claim photos come from different cameras: "
                      f"{', '.join(known)}.", {"cameras": known}, tier="claim")
    return Signal(name, 0.0, 0.6, f"All photos come from the same camera ({known[0]}).",
                  {"cameras": known}, tier="claim")


def name_mismatch(id_name: str | None, doc_names: list[str]) -> Signal:
    from rapidfuzz import fuzz

    name = "name_mismatch"
    doc_names = [n for n in doc_names if n]
    if not id_name or not doc_names:
        return Signal(name, None, 0.0, "Not applicable: needs a name on the ID and on a document.",
                      applicable=False, tier="claim")
    sims = {n: fuzz.token_sort_ratio(id_name.lower(), n.lower()) for n in doc_names}
    worst = min(sims, key=sims.get)
    ev = {"id_name": id_name, "similarity": sims}
    if sims[worst] < NAME_MIN_SIMILARITY:
        return Signal(name, 1.0, 0.7, f"The name on the ID ({id_name}) differs from the name on "
                      f"a claim document ({worst}).", ev, tier="claim")
    return Signal(name, 0.0, 0.7, "The name on the ID matches the claim documents.", ev, tier="claim")
