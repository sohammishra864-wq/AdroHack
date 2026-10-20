import cv2
import numpy as np
import pytest
from PIL import Image
from PIL.ExifTags import Base

from claimshield.preprocess import prepare
from claimshield.signals.forensics import copy_move, jpeg_qtables, noise_residual


def texture(w=512, h=512, seed=0):
    n = np.random.default_rng(seed).integers(0, 255, (h, w), np.uint8)
    return cv2.GaussianBlur(n, (0, 0), 2)


def save(tmp_path, name, arr, **kw):
    p = tmp_path / name
    Image.fromarray(arr).convert("RGB").save(p, **kw)
    return prepare(str(p))


# --- jpeg_qtables -----------------------------------------------------------------------
def test_qtables_not_applicable_on_png(tmp_path):
    s = jpeg_qtables.run(save(tmp_path, "a.png", texture()))
    assert not s.applicable and s.score is None


def test_ijg_table_matches_pil(tmp_path):
    p = tmp_path / "q75.jpg"
    Image.fromarray(texture()).save(p, quality=75)
    assert jpeg_qtables.is_standard(list(Image.open(p).quantization[0]), 75)


def test_camera_exif_with_software_tables_flags(tmp_path):
    e = Image.Exif()
    e[Base.Make] = "Apple"
    s = jpeg_qtables.run(save(tmp_path, "cam.jpg", texture(seed=1), quality=90, exif=e))
    assert s.score >= 0.6 and "Apple" in s.reason


# --- copy_move --------------------------------------------------------------------------
def test_copy_move_detects_duplicated_patch(tmp_path):
    a = texture(seed=2)
    a[300:400, 320:420] = a[50:150, 50:150]
    s = copy_move.run(save(tmp_path, "cm.png", a))
    assert s.score >= 0.8 and len(s.evidence["boxes"]) == 2


def test_copy_move_clean_texture(tmp_path):
    assert copy_move.run(save(tmp_path, "clean.png", texture(seed=3))).score < 0.5


# --- noise_residual ---------------------------------------------------------------------
def flat_with_noise(sigma_bg, sigma_patch, seed=0):
    rng = np.random.default_rng(seed)
    a = 128 + rng.normal(0, sigma_bg, (512, 512))
    a[128:256, 128:256] = 128 + rng.normal(0, sigma_patch, (128, 128))
    return np.clip(a, 0, 255).astype(np.uint8)


def test_noise_residual_flags_patch_with_different_noise(tmp_path):
    s = noise_residual.run(save(tmp_path, "np.png", flat_with_noise(3, 20)))
    assert s.score >= 0.65 and s.evidence["largest_frac"] >= 0.05


def test_noise_residual_uniform_is_clean(tmp_path):
    assert noise_residual.run(save(tmp_path, "nu.png", flat_with_noise(3, 3, seed=1))).score < 0.5


# --- c2pa -------------------------------------------------------------------------------
def test_c2pa_absent_is_not_applicable(tmp_path):
    pytest.importorskip("c2pa")
    from claimshield.signals.forensics import c2pa

    s = c2pa.run(save(tmp_path, "plain.jpg", texture(), quality=90))
    assert not s.applicable and s.score is None
