"""UI smoke test: the app renders its four tabs without an exception (no claim open)."""
from pathlib import Path

import pytest

APP = str(Path(__file__).resolve().parents[1] / "claimshield" / "ui" / "app.py")


def test_app_renders():
    pytest.importorskip("cv2")
    testing = pytest.importorskip("streamlit.testing.v1")
    at = testing.AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert len(at.tabs) == 4
