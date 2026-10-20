"""Arena fallback chain with the network on and off (attack functions monkeypatched)."""
import io

import numpy as np
import pytest
from PIL import Image

from claimshield.arena import attacks


@pytest.fixture
def photo(tmp_path, monkeypatch):
    p = tmp_path / "p.jpg"
    Image.new("RGB", (640, 480), (120, 130, 140)).save(p)
    cfg = {**attacks._cfg(), "pregenerated_dir": str(tmp_path / "pre")}
    monkeypatch.setattr(attacks, "_cfg", lambda: cfg)
    return p


def boom(*a, **k):
    raise ConnectionError("network off")


def test_network_on_uses_nova(photo, monkeypatch):
    monkeypatch.setattr(attacks, "inpaint_nova", lambda img, p, m: img)
    monkeypatch.setattr(attacks, "inpaint_local_sd15", boom)
    a = attacks.inpaint(photo)
    assert a.method == "nova" and a.kind == "inpaint"
    assert Image.open(io.BytesIO(a.data)).format == "JPEG"


def test_bedrock_off_falls_back_to_local(photo, monkeypatch):
    monkeypatch.setattr(attacks, "inpaint_nova", boom)
    monkeypatch.setattr(attacks, "inpaint_local_sd15", lambda img, p: img)
    assert attacks.inpaint(photo).method == "local_sd15"


def test_everything_off_uses_pregenerated_or_says_so(photo, tmp_path, monkeypatch):
    monkeypatch.setattr(attacks, "inpaint_nova", boom)
    monkeypatch.setattr(attacks, "inpaint_local_sd15", boom)
    with pytest.raises(RuntimeError, match="no attack path"):
        attacks.inpaint(photo)
    (tmp_path / "pre").mkdir()
    (tmp_path / "pre" / "inpaint_nova_x.jpg").write_bytes(b"jpegbytes")
    a = attacks.inpaint(photo)
    assert a.method == "pregenerated" and a.data == b"jpegbytes" and "before the demo" in a.note


def test_recompress_q70(photo):
    a = attacks.recompress_q70(photo)
    img = Image.open(io.BytesIO(a.data))
    assert a.method == "recompress" and img.format == "JPEG" and img.size == (640, 480)


def test_damage_mask_covers_about_ten_percent():
    m = attacks.damage_mask((1000, 800))
    frac = (np.asarray(m) > 0).mean()
    assert 0.07 < frac < 0.13
