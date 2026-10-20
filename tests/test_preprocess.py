import numpy as np
import pytest
from PIL import Image

from claimshield.preprocess import estimate_jpeg_quality, prepare


def noise(w, h, seed=0):
    return Image.fromarray(np.random.default_rng(seed).integers(0, 255, (h, w, 3), np.uint8))


@pytest.mark.parametrize("q", [30, 60, 95])
def test_jpeg_quality_estimate(tmp_path, q):
    p = tmp_path / f"q{q}.jpg"
    noise(64, 64).save(p, quality=q)
    assert abs(estimate_jpeg_quality(Image.open(p)) - q) <= 2


def test_png_has_no_jpeg_quality(tmp_path):
    p = tmp_path / "a.png"
    noise(64, 64).save(p)
    assert estimate_jpeg_quality(Image.open(p)) is None


def test_tiny_image_trips_quality_gate(tmp_path):
    p = tmp_path / "tiny.jpg"
    noise(100, 100, seed=1).save(p, quality=95)
    prep = prepare(str(p))
    assert prep.quality_flag and "256" in prep.quality_reasons[0]


def test_blurry_image_trips_quality_gate(tmp_path):
    p = tmp_path / "flat.png"
    Image.new("RGB", (600, 400), (120, 120, 120)).save(p)
    assert "blurry" in " ".join(prepare(str(p)).quality_reasons)


def test_good_image_passes_and_is_resized(tmp_path):
    p = tmp_path / "big.jpg"
    noise(2000, 1500, seed=2).save(p, quality=92)
    prep = prepare(str(p))
    assert not prep.quality_flag
    assert max(prep.rgb.size) == 1024 and prep.orig_size == (2000, 1500)
    assert prepare(str(p)) is prep  # sha256 cache
