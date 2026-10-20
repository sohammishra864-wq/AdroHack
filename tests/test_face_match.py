"""Face match without weights: embed() is monkeypatched."""
import numpy as np

from claimshield.signals.identity import face_match


def unit(*v):
    v = np.array(v, np.float32)
    return v / np.linalg.norm(v)


def test_match_mismatch_and_no_face(monkeypatch):
    faces = {"id": (unit(1, 0, 0), 0.9), "same": (unit(1, 0.1, 0), 0.9),
             "other": (unit(0, 1, 0), 0.9), "none": None}
    monkeypatch.setattr(face_match, "embed", lambda key: faces[key])
    ok, bad, na = (face_match.run("id", k) for k in ("same", "other", "none"))
    assert ok.score < 0.05 and "matches" in ok.reason and ok.tier == "identity"
    assert bad.score > 0.95 and "does not match" in bad.reason
    assert not na.applicable and "the selfie" in na.reason
