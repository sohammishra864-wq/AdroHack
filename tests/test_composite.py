import pytest

from claimshield.contracts import Signal
from claimshield.scoring.composite import score_claim


def sig(name, score, conf=1.0, tier="fast", **kw):
    return Signal(name, score, conf, "r", tier=tier, **kw)


@pytest.mark.parametrize("score,band", [(0.1, "LOW"), (0.5, "MEDIUM"), (0.9, "HIGH")])
def test_bands(score, band):
    assert score_claim([sig("localizer", score)]).band == band


def test_not_applicable_and_abstained_are_ignored():
    base = score_claim([sig("localizer", 0.9)]).overall
    extra = [sig("jpeg_qtables", None, applicable=False), sig("clip_probe", None, abstained=True)]
    assert score_claim([sig("localizer", 0.9), *extra]).overall == pytest.approx(base)


def test_quality_gate_forces_uncertain_unless_strong_evidence():
    assert score_claim([sig("localizer", 0.9)], quality_flag=True).band == "UNCERTAIN"
    with_c2pa = [sig("localizer", 0.9), sig("c2pa", 0.95)]
    assert score_claim(with_c2pa, quality_flag=True).band == "HIGH"


def test_nothing_usable_is_uncertain():
    assert score_claim([sig("exif", None, applicable=False)]).band == "UNCERTAIN"


def test_quality_gate_caps_fast_confidence():
    s = [sig("localizer", 0.9, 1.0), sig("clip_probe", 0.1, 0.5)]
    # capped to 0.5 each → localizer's pull shrinks
    assert score_claim(s, quality_flag=True).image_score < score_claim(s).image_score


def test_waterfall_sums_to_overall():
    s = [sig("localizer", 0.9), sig("clip_probe", 0.2, 0.6), sig("exif", 0.55, 0.15),
         sig("pdf_incremental_update", 0.95, tier="doc"), sig("field_arithmetic", 0.1, tier="doc"),
         sig("invoice_before_photo", 1.0, tier="claim")]
    cs = score_claim(s)
    assert cs.waterfall[0] == ("baseline", 0.5)
    assert sum(v for _, v in cs.waterfall) == pytest.approx(cs.overall)
    assert any(v < 0 for _, v in cs.waterfall)  # authentic votes show as negative bars


def test_unknown_signal_names_are_ignored():
    assert score_claim([sig("not_in_weights", 1.0)]).band == "UNCERTAIN"
