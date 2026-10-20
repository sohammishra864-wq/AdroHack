"""Eval harness on synthetic cached results (no models, no images)."""
import argparse
import importlib.util
import random
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("eval_script", ROOT / "scripts" / "eval.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def test_wilson_interval():
    lo, hi = ev.wilson(5, 100)
    assert 0.02 < lo < 0.05 < hi < 0.12
    assert ev.wilson(0, 1500)[0] == pytest.approx(0, abs=1e-12)


@pytest.fixture
def world(tmp_path, monkeypatch):
    pytest.importorskip("sklearn")
    from claimshield import config

    shutil.copytree(ROOT / "configs", tmp_path / "configs")
    (tmp_path / "configs" / "calibration.yaml").unlink(missing_ok=True)
    monkeypatch.setattr(ev, "ROOT", tmp_path)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    config.cfg.cache_clear()
    yield tmp_path
    config.cfg.cache_clear()


def fake_world():
    rng, rows, res = random.Random(0), [], {}
    spec = [("calib", "real", "real", "0", 60), ("calib", "fake", "sd15", "0", 60),
            ("test", "real", "real", "0", 80), ("test", "fake", "sd15", "0", 80),
            ("test", "fake", "flux", "1", 40), ("wild", "real", "real", "0", 100),
            ("eval_only", "fake", "gan", "0", 20)]
    for split, label, fam, held, n in spec:
        for i in range(n):
            path = f"data/{split}/{fam}/{'faces/' if split == 'wild' and i < 10 else ''}{i}.jpg"
            rows.append({"path": path, "label": label, "family": fam, "attack": "t2i",
                         "quality": "orig", "heldout": held, "split": split,
                         "seed_path": "", "mask_path": ""})
            s = min(1, max(0, rng.gauss(0.75 if label == "fake" else 0.25, 0.15)))
            res[path] = {"quality_flag": False, "iou": {},
                         "signals": {"clip_probe": [s, 0.8, True, False, "fast"],
                                     "c2pa": [None, 0.0, False, False, "fast"]},
                         "family": {"leaf": "sd15" if s > 0.5 else "real", "diffusion": s, "real": 1 - s}}
    return rows, res


def args(**kw):
    return argparse.Namespace(manifest="m.csv", out="reports/eval_latest.md", subset=None,
                              impls=["fallback"], **kw)


def test_report_has_all_nine_sections_and_never_reports_calib(world):
    rows, res = fake_world()
    ev.report([r for r in rows if r["split"] != "calib"], res, ["clip_probe", "c2pa"], [], args(), "")
    md = (world / "reports" / "eval_latest.md").read_text(encoding="utf-8")
    for h in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6.", "## 7.", "## 8.", "## 9."):
        assert h in md
    assert "| test-heldout (Flux) | 40 | 80 |" in md and "gan (eval-only)" in md
    assert "No calibration file" in md
    table = __import__("json").loads((world / "reports" / "heldout_table.json").read_text())
    assert table["families"]["flux"]["heldout"] and table["families"]["flux"]["n"] == 40
    assert table["families"]["gan"]["eval_only"] and "orig" in table["robustness"]


def test_calibration_is_fitted_on_calib_only_and_applied(world):
    rows, res = fake_world()
    note = ev.calibrate(rows, res, ["clip_probe", "c2pa"])
    cal = (world / "configs" / "calibration.yaml").read_text(encoding="utf-8")
    assert "clip_probe" in cal and "c2pa" not in cal and "n: 120" in cal
    assert "NOT applied" in note

    from claimshield.scoring.composite import calibration, calibrated
    c = calibration()
    assert calibrated("clip_probe", 0.9, c) > calibrated("clip_probe", 0.1, c)
    assert calibrated("exif", 0.3, c) == 0.3  # uncalibrated signals pass through
