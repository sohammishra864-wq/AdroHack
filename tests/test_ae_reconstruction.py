"""AE reconstruction without weights: distance() is monkeypatched."""
import numpy as np
import pytest
from PIL import Image

from claimshield.preprocess import prepare
from claimshield.signals import ae_reconstruction as ae


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "p.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (300, 400, 3), np.uint8)).save(p)
    return prepare(str(p))


def fake_distance(d):
    return lambda rgb, name, px: (d, np.full((48, 64), d, np.float32))


def test_low_error_scores_high_with_capped_confidence_and_fixed_text(monkeypatch, photo):
    monkeypatch.setattr(ae, "distance", fake_distance(0.0))
    s = ae.run(photo)
    assert s.score > 0.95 and s.confidence == 0.7 and s.tier == "deep"
    assert s.reason == ("Reconstruction test: low error. Most informative for "
                        "diffusion-generated images; treated as supporting evidence.")
    assert s.evidence["patch_map"].shape == (300, 400)


def test_high_error_text(monkeypatch, photo):
    monkeypatch.setattr(ae, "distance", fake_distance(0.2))
    s = ae.run(photo)
    assert s.score < 0.05 and s.confidence <= 0.7
    assert s.reason.startswith("Reconstruction test: high error.")


def test_min_over_vaes(monkeypatch, photo):
    monkeypatch.setattr(ae, "_vaes", lambda: ("sd15", "sdxl", "flux"))
    ds = {"sd15": 0.05, "sdxl": 0.01, "flux": 0.03}
    monkeypatch.setattr(ae, "distance", lambda rgb, n, px: (ds[n], np.zeros((8, 8), np.float32)))
    s = ae.run(photo)
    assert s.evidence["vae"] == "sdxl" and s.evidence["distance"] == 0.01
