"""The three claim-level checks, one test each."""
from datetime import date, datetime

import pytest

from claimshield.claim import consistency as c


def test_invoice_before_photo():
    s = c.invoice_before_photo([date(2026, 3, 1)], [datetime(2026, 3, 5, 10), datetime(2026, 3, 6)])
    assert s.score == 1.0 and "before" in s.reason
    assert c.invoice_before_photo([date(2026, 3, 9)], [datetime(2026, 3, 5)]).score == 0.0
    assert not c.invoice_before_photo([], [datetime(2026, 3, 5)]).applicable


def test_camera_model_mismatch():
    assert c.camera_model_mismatch(["Apple iPhone 13", "Samsung SM-G991B"]).score == 1.0
    assert c.camera_model_mismatch(["Apple iPhone 13", "Apple iPhone 13"]).score == 0.0
    assert not c.camera_model_mismatch(["Apple iPhone 13", ""]).applicable


def test_name_mismatch():
    pytest.importorskip("rapidfuzz")
    assert c.name_mismatch("Asha Verma", ["Verma Asha"]).score == 0.0
    s = c.name_mismatch("Asha Verma", ["Rahul Nair"])
    assert s.score == 1.0 and "Rahul Nair" in s.reason
    assert not c.name_mismatch(None, ["Rahul Nair"]).applicable
