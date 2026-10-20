"""Cross-claim check through the REAL pipeline.combine + composite: scoring rules, the
provisional pass never stores, the final pass does, and a reused photo moves the band."""
import io
from dataclasses import dataclass, field

import numpy as np
import pytest
from PIL import Image

from claimshield import config, memory, pipeline
from claimshield.contracts import Signal
from claimshield.scoring.composite import score_claim
from claimshield.signals import cross_claim as cc

W = config.cfg("weights")["claim"]["cross_claim"]


def photo(seed=3):
    small = np.random.default_rng(seed).integers(0, 256, (6, 8, 3), dtype=np.uint8)
    return Image.fromarray(small).resize((800, 600), Image.Resampling.BICUBIC)


def whatsapp(im):
    buf = io.BytesIO()
    im.resize((400, 300)).save(buf, "JPEG", quality=40)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def real_photo_result(rgb):
    """An ImageResult whose own checks say 'authentic' (overall ≈ 0.25)."""
    sigs = [Signal("localizer", 0.25, 0.8, "No edited area."),
            Signal("clip_probe", 0.25, 0.8, "Looks like a camera photo.")]
    return pipeline.ImageResult(score_claim(sigs), "ab" * 32, [], 0.1, 0.2, rgb=rgb)


@dataclass
class Doc:
    text: str
    doc_type: str = "invoice"
    claim: object = field(default_factory=lambda: score_claim([]))


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "DB", tmp_path / "audit.sqlite")
    return tmp_path / "audit.sqlite"


def test_rules_table():
    L = lambda case, *kinds: [{"case_id": case, "kind": k, "value": "", "ts": "2026-10-01"} for k in kinds]  # noqa: E731
    assert cc.strongest(L("a", "photo"))[0] == 1.0
    assert cc.strongest(L("a", "vin", "vendor"))[0] == 0.9
    assert cc.strongest(L("a", "vin"))[0] == 0.6
    assert cc.strongest(L("a", "vendor"))[:2] == (0.0, "a")          # shop alone: shown, not scored
    assert cc.strongest(L("a", "vendor") + L("b", "claimant"))[:2] == (0.3, "b")


def test_not_applicable_without_case_id_and_nothing_stored(db):
    s = cc.run(None, {"photo": ["f0e1d2c3b4a59687"]})
    assert not s.applicable and s.score is None
    assert memory.links("x", {"photo": ["f0e1d2c3b4a59687"]}) == []


def test_reused_photo_through_combine_moves_band(db):
    img = photo()
    a = pipeline.combine([real_photo_result(img)], [], [], case_id="case-a")          # provisional
    assert memory.links("case-z", {"photo": [cc.phash(img)]}) == []                  # not stored yet
    a = pipeline.combine([real_photo_result(img)], [], [], case_id="case-a", remember=True)
    ring_a = next(s for s in a.claim.signals if s.name == "cross_claim")
    assert ring_a.score == 0.0 and a.claim.band == "LOW"

    b = pipeline.combine([real_photo_result(whatsapp(img))], [], [], case_id="case-b", remember=True)
    ring_b = next(s for s in b.claim.signals if s.name == "cross_claim")
    assert ring_b.score == 1.0 and "case-a" in ring_b.reason and "same photo" in ring_b.reason
    assert b.claim.overall == pytest.approx(a.claim.overall + W * 0.9)
    assert b.claim.band == "HIGH"
    assert ("cross_claim", pytest.approx(W * 0.9)) in b.claim.waterfall

    again = pipeline.combine([real_photo_result(img)], [], [], case_id="case-a", remember=True)
    assert next(s for s in again.claim.signals if s.name == "cross_claim").score == 1.0  # B links back


def test_shared_shop_and_vin_without_photo(db):
    inv = "Speedline Auto Repairs INVOICE\nBill to\nAsha Verma\nVIN: MA3EYD32S00123456"
    pipeline.combine([], [Doc(inv)], [], case_id="case-a", remember=True)
    b = pipeline.combine([], [Doc(inv.replace("Asha Verma", "Rahul Nair"))], [], case_id="case-b")
    s = next(s for s in b.claim.signals if s.name == "cross_claim")
    assert s.score == 0.9 and "Speedline Auto Repairs" in s.reason
    assert "MA3EYD32S00123456" not in s.reason and "Asha" not in s.reason   # no PII in the narrative


MED = """St. Anne's Multispeciality Hospital
DISCHARGE SUMMARY
Patient: Meera Pillai
Admitted: {adm}
Discharged: 09/07/2026
Diagnosis
Fracture of rib (ICD-10 S22.3)"""


def test_same_stay_twice_is_flagged_but_a_legit_followup_is_not(db):
    first = Doc(MED.format(adm="05/07/2026"), "medical")
    pipeline.combine([], [first], [], case_id="h1", remember=True)
    dup = pipeline.combine([], [Doc(MED.format(adm="05/07/2026"), "medical")], [], case_id="h2")
    s = next(x for x in dup.claim.signals if x.name == "cross_claim")
    assert s.score == 1.0 and "same hospital stay" in s.reason and "Meera" not in s.reason
    follow = pipeline.combine([], [Doc(MED.format(adm="14/09/2026"), "medical")], [], case_id="h4")
    f = next(x for x in follow.claim.signals if x.name == "cross_claim")
    assert f.score == 0.3                                   # same patient + hospital, new stay: small bump only
    assert f.score * W * 0.9 < 0.2                          # adds < 0.2 to the overall: a clean claim stays LOW
