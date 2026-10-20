"""Fraud-ring demo cases from REAL generated PDFs: the text layer gives back the shop, VIN and
claimant; r2's photo is a pHash match of r1's; r1 and r3 share shop + VIN; memory reset."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

pytest.importorskip("pikepdf")
pytest.importorskip("pdfplumber")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "gen"))
import ring_cases  # noqa: E402

from claimshield import memory  # noqa: E402
from claimshield.signals import cross_claim as cc  # noqa: E402
from claimshield.signals.documents import doc_type, pdf_structure  # noqa: E402


def seed(path, n):
    small = np.random.default_rng(n).integers(0, 256, (6, 8, 3), dtype=np.uint8)
    Image.fromarray(small).resize((1024, 768), Image.Resampling.BICUBIC).save(path, quality=95)
    return path


def read(d):
    text = pdf_structure.text_of((d / "invoice.pdf").read_bytes())
    kind = doc_type.classify(text)
    return text, kind


def test_ring_cases_round_trip(tmp_path):
    r1, r2, r3 = ring_cases.build(seed(tmp_path / "a.jpg", 1), seed(tmp_path / "b.jpg", 2), tmp_path / "cases")
    t1, k1 = read(r1)
    t3, k3 = read(r3)
    assert k1 == k3 == "invoice"
    assert cc.vendor(t1, k1) == cc.vendor(t3, k3) == "Speedline Auto Repairs"
    assert cc.vins(t1) == cc.vins(t3) == [ring_cases.VIN]
    t2, k2 = read(r2)
    assert cc.vendor(t2, k2) == "Northgate Glass & Glazing" and cc.vins(t2) == []

    p1 = cc.phash(Image.open(r1 / "photo.jpg").convert("RGB"))
    p2 = cc.phash(Image.open(r2 / "photo.jpg").convert("RGB"))
    assert bin(int(p1, 16) ^ int(p2, 16)).count("1") <= memory.PHASH_MAX_DIST
