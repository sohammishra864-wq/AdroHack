"""EXIF check: editing software, missing camera make/model, edit-after-capture gap.

Missing EXIF alone is weak evidence (WhatsApp and most social apps strip it).
"""
from __future__ import annotations

from datetime import datetime

from PIL.ExifTags import Base, IFD

from ...contracts import Signal

NAME = "exif"
EDITORS = ("photoshop", "gimp", "lightroom", "firefly", "midjourney", "stable diffusion",
           "dall", "canva", "picsart", "snapseed", "facetune", "affinity", "pixelmator")
PHONE_RES_PX = 8_000_000


def _dt(v) -> datetime | None:
    try:
        return datetime.strptime(str(v).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def run(prep) -> Signal:
    exif = prep.exif
    if not exif and prep.fmt in ("PNG", "WEBP"):
        return Signal(NAME, None, 0.0, f"Not applicable: {prep.fmt} files normally carry "
                      "no camera metadata.", applicable=False)

    make = str(exif.get(Base.Make, "")).strip("\x00 ")
    model = str(exif.get(Base.Model, "")).strip("\x00 ")
    software = str(exif.get(Base.Software, "")).strip("\x00 ")
    shot = _dt(exif.get_ifd(IFD.Exif).get(Base.DateTimeOriginal, "")) if exif else None
    saved = _dt(exif.get(Base.DateTime, ""))
    ev = {"make": make, "model": model, "software": software,
          "datetime_original": shot.isoformat() if shot else None}

    if any(e in software.lower() for e in EDITORS):
        return Signal(NAME, 0.8, 0.6, f"The file's metadata says it was last saved by "
                      f"{software}.", ev)
    if not exif:
        return Signal(NAME, 0.55, 0.15, "No camera metadata. Common after WhatsApp or "
                      "social-media sharing, so this is weak evidence.", ev)
    w, h = prep.orig_size
    if not (make or model) and w * h >= PHONE_RES_PX:
        return Signal(NAME, 0.65, 0.3, f"Full camera resolution ({w}×{h}) but no camera "
                      "make or model recorded.", ev)
    if shot and saved and (saved - shot).days >= 1:
        return Signal(NAME, 0.6, 0.3, f"Saved again {(saved - shot).days} days after the "
                      "photo was taken.", ev)
    cam = f"{make} {model}".strip() or "camera"
    return Signal(NAME, 0.2, 0.4, f"Camera metadata intact ({cam}); no editing software "
                  "recorded.", ev)
