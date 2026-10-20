import numpy as np
import pytest
from PIL import Image

from claimshield import config
from claimshield.preprocess import prepare
from claimshield.signals import localizer
from claimshield.signals.localizer import fallback
from claimshield.signals.localizer.base import LocResult


class Fake:
    name = "fake"

    def warm(self):
        pass

    def __call__(self, rgb):
        h = np.zeros((64, 64), np.float32)
        h[16:48, 16:48] = 0.95
        return LocResult(h, np.ones_like(h), 0.9)


@pytest.fixture
def photo(tmp_path):
    p = tmp_path / "p.png"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (300, 400, 3), np.uint8)).save(p)
    return prepare(str(p))


def test_signal_wrapper_resizes_heatmap_and_flags(monkeypatch, photo):
    monkeypatch.setattr(localizer, "current", lambda: Fake())
    s = localizer.run(photo)
    assert s.name == "localizer" and s.score == 0.9
    assert s.evidence["heatmap"].shape == (300, 400)
    assert s.evidence["area_frac"] == pytest.approx(0.25, abs=0.03)


def test_config_switches_implementation(monkeypatch):
    impl = config.cfg("thresholds")["localizer"]["impl"]
    assert impl in ("trufor", "fallback")
    with pytest.raises(ValueError):
        localizer.get("nope")


def test_fallback_unions_ae_and_noise(monkeypatch, photo):
    ae = np.zeros((300, 400), np.float32)
    ae[100:200, 100:200] = 1.0
    monkeypatch.setattr(fallback.vae, "low_error_map", lambda rgb, px: ae)
    r = fallback.Fallback()(photo.rgb)
    assert r.heatmap.shape == (300, 400) and r.heatmap[150, 150] == 1.0
    assert 0.0 <= r.integrity <= 1.0
