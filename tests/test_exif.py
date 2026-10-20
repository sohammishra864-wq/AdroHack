import numpy as np
from PIL import Image
from PIL.ExifTags import Base

from claimshield.preprocess import prepare
from claimshield.signals.forensics import exif


def photo(tmp_path, name, tags=None, fmt=None):
    img = Image.fromarray(np.random.default_rng(0).integers(0, 255, (400, 600, 3), np.uint8))
    e = Image.Exif()
    for k, v in (tags or {}).items():
        e[k] = v
    p = tmp_path / name
    img.save(p, format=fmt, exif=e) if tags else img.save(p, format=fmt)
    return exif.run(prepare(str(p)))


def test_png_without_exif_is_not_applicable(tmp_path):
    s = photo(tmp_path, "shot.png")
    assert not s.applicable and s.score is None


def test_stripped_jpeg_is_weak_evidence(tmp_path):
    s = photo(tmp_path, "wa.jpg")
    assert s.applicable and s.confidence <= 0.2


def test_editing_software_flags(tmp_path):
    s = photo(tmp_path, "ps.jpg", {Base.Software: "Adobe Photoshop 25.0"})
    assert s.score >= 0.65 and "Photoshop" in s.reason


def test_camera_metadata_intact_reads_authentic(tmp_path):
    s = photo(tmp_path, "cam.jpg", {Base.Make: "Apple", Base.Model: "iPhone 14"})
    assert s.score < 0.35 and s.evidence["model"] == "iPhone 14"
