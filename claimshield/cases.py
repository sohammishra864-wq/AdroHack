"""Inbox: one folder per claim under data/cases/<case_id>/.

File roles by name: id.* / id_* → ID document image; selfie.* → selfie; *.pdf or a name starting
with invoice / receipt / medical / report / doc / scan → document; other images → photos.
Optional case.json: {"title": "...", "description": "what happened"}. The last band per case is kept in
data/cache/case_bands.json so the inbox shows chips across restarts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from . import config

CASES = config.ROOT / "data" / "cases"
BANDS = config.ROOT / "data" / "cache" / "case_bands.json"
IMAGES = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
DOC_PREFIX = ("invoice", "receipt", "medical", "report", "doc", "scan")


@dataclass
class Case:
    id: str
    title: str
    photos: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    id_path: str | None = None
    selfie: str | None = None
    description: str = ""    # what the claimant says happened (case.json); damage_story check

    def files(self) -> list[str]:
        return [*self.photos, *self.docs, *filter(None, (self.id_path, self.selfie))]


def load(d: Path, case_id: str | None = None) -> Case:
    meta = json.loads((d / "case.json").read_text(encoding="utf-8")) if (d / "case.json").exists() else {}
    c = Case(case_id or d.name, meta.get("title", d.name), description=meta.get("description", ""))
    for f in sorted(p for p in d.iterdir() if p.is_file()):
        stem, ext = f.stem.lower(), f.suffix.lower()
        if ext in IMAGES and (stem == "id" or stem.startswith(("id_", "id-"))):
            c.id_path = str(f)
        elif ext in IMAGES and stem.startswith("selfie"):
            c.selfie = str(f)
        elif ext == ".pdf" or (ext in IMAGES and stem.startswith(DOC_PREFIX)):
            c.docs.append(str(f))
        elif ext in IMAGES:
            c.photos.append(str(f))
    return c


def inbox() -> list[Case]:
    return [load(d) for d in sorted(CASES.iterdir()) if d.is_dir()] if CASES.exists() else []


def hashes(case: Case) -> list[str]:
    return [hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in case.files()]


def last_bands() -> dict:
    return json.loads(BANDS.read_text()) if BANDS.exists() else {}


def save_band(case_id: str, band: str) -> None:
    b = last_bands() | {case_id: band}
    BANDS.parent.mkdir(parents=True, exist_ok=True)
    BANDS.write_text(json.dumps(b))
