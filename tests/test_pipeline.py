"""End-to-end without model weights: missing models become grey cards, never a crash."""
import threading

import numpy as np
import pytest
from PIL import Image

from claimshield import pipeline
from claimshield.contracts import Signal


def ae(score=0.9):
    return Signal("ae_reconstruction", score, 0.7, "r", tier="deep")


@pytest.fixture
def photo(tmp_path, monkeypatch):
    monkeypatch.setattr(pipeline.ae_reconstruction, "run", lambda prep: ae())  # no VAE download
    p = tmp_path / "x.jpg"
    Image.fromarray(np.random.default_rng(0).integers(0, 255, (600, 800, 3), np.uint8)).save(p)
    return p


def test_cards_stream_in_order_and_missing_models_abstain(photo):
    p = photo
    seen = []
    res = pipeline.score_image(str(p), on_card=lambda s: seen.append(s.name))

    order = [fn.__module__.rsplit(".", 1)[-1] for g in ("forensics", "clip_probe", "localizer")
             for fn in pipeline.FAST[g]]
    assert seen == order
    assert res.claim.band in ("LOW", "MEDIUM", "HIGH", "UNCERTAIN")
    assert res.t_first <= res.t_fast
    for s in res.claim.signals:
        assert s.score is not None or s.reason  # grey cards always explain themselves


def test_deep_tier_never_blocks_fast_and_lands_later(photo, monkeypatch):
    gate = threading.Event()
    monkeypatch.setattr(pipeline.ae_reconstruction, "run", lambda prep: gate.wait(10) and ae())
    res = pipeline.score_image(str(photo))      # returns while the AE job is still blocked
    assert res.claim.pending_deep and res.t_deep is None
    assert "ae_reconstruction" not in [s.name for s in res.claim.signals]
    gate.set()
    done = pipeline.finish(res)
    assert not done.claim.pending_deep and done.t_deep is not None
    assert done.claim.signals[-1].name == "ae_reconstruction"
    assert any(k == "ae_reconstruction" for k, _ in done.claim.waterfall)


def test_wait_deep_fills_t_deep_for_bench(photo):
    res = pipeline.score_image(str(photo), wait_deep=True)
    assert res.t_deep is not None and not res.claim.pending_deep
