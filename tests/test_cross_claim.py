"""Cross-claim entity extraction: pHash tolerance, VIN / vendor / claimant from document text,
and the two-claim fraud-ring link through memory.py."""
import io
from types import SimpleNamespace

import numpy as np
from PIL import Image

from claimshield import memory
from claimshield.signals import cross_claim as cc

INVOICE = """Speedline Auto Repairs INVOICE
42 Industrial Estate, Pune 411045 No. INV-202600017
Date: 14/03/2026
Bill to
Asha Verma
Claim ref CLM-482913
VIN: MA3 EYD32S0O1234 56
Rear bumper replacement 1 18,000.00 18,000.00"""
MEDICAL = """St. Anne's Multispeciality Hospital
DISCHARGE SUMMARY
Patient: Asha Verma
Diagnosis: Fracture of radius (ICD-10 S52.5)"""


def photo(seed: int) -> Image.Image:
    """A smooth random 'scene' (photo-like low frequencies, not white noise)."""
    small = np.random.default_rng(seed).integers(0, 256, (6, 8, 3), dtype=np.uint8)
    return Image.fromarray(small).resize((800, 600), Image.Resampling.BICUBIC)


def whatsapp(im: Image.Image) -> Image.Image:
    buf = io.BytesIO()
    im.resize((im.width // 2, im.height // 2)).save(buf, "JPEG", quality=40)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def dist(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def test_phash_matches_recompressed_copy_not_other_photos():
    a = photo(1)
    assert dist(cc.phash(a), cc.phash(whatsapp(a))) <= memory.PHASH_MAX_DIST
    assert all(dist(cc.phash(a), cc.phash(photo(s))) > memory.PHASH_MAX_DIST for s in range(2, 12))
    assert len(cc.phash(a)) == 16


def test_vin_labelled_with_ocr_slips_and_bare():
    assert cc.vins(INVOICE) == ["MA3EYD32S00123456"]          # spaces + O-for-0 fixed
    assert cc.vins("chassis no. 1HGCM82633A004352 reg MH12") == ["1HGCM82633A004352"]
    assert cc.vins("GSTIN 27AAPFU0939F1ZV  INV-202600017  12345678901234567") == []  # no letters


def test_vendor_letterhead_label_and_other_docs():
    assert cc.vendor(INVOICE, "invoice") == "Speedline Auto Repairs"
    assert cc.vendor(MEDICAL, "medical") == "St. Anne's Multispeciality Hospital"
    assert cc.vendor("Some letter\nGarage: Shree Auto Works", "other") == "Shree Auto Works"
    assert cc.vendor("Some letter\nnothing here", "other") is None


def test_two_claims_sharing_shop_and_photo_are_linked(tmp_path):
    db, img = tmp_path / "m.sqlite", photo(7)
    claim_a = cc.entities([SimpleNamespace(rgb=img)], [SimpleNamespace(text=INVOICE, doc_type="invoice")])
    assert claim_a["vendor"] == ["Speedline Auto Repairs"] and claim_a["claimant"] == ["Asha Verma"]
    memory.remember("case-a", claim_a, path=db)

    other = INVOICE.replace("Asha Verma", "Rahul Nair").replace("MA3 EYD32S0O1234 56", "")
    claim_b = cc.entities([SimpleNamespace(rgb=whatsapp(img))], [SimpleNamespace(text=other, doc_type="invoice")])
    got = memory.links("case-b", claim_b, path=db)
    assert sorted(l["kind"] for l in got) == ["photo", "vendor"]
    assert {l["case_id"] for l in got} == {"case-a"}
    assert memory.links("case-c", cc.entities([SimpleNamespace(rgb=photo(8))], []), path=db) == []
