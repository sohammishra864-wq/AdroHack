"""Damage vs story: story parsing, legit stories never flagged, clear contradictions flagged,
and with several photos the best-matching one decides. No CLIP needed (photo reads injected)."""
import numpy as np

from claimshield.signals import damage_story as ds


def read(sev, front):
    """A photo read: expected severity ≈ sev (0..3), front-vs-rear probability `front`."""
    p = np.zeros(4)
    lo = int(np.floor(sev))
    hi = min(lo + 1, 3)
    p[lo], p[hi] = p[lo] + (hi - sev if hi != lo else 1), p[hi] + (sev - lo if hi != lo else 0)
    return p, np.array([front, 1 - front])


def test_story_parsing():
    assert ds.story_claims("I was rear-ended at 60 km/h") == ("rear", 3)
    assert ds.story_claims("hit the car in front at 10 kmph") == ("front", 1)
    assert ds.story_claims("car was parked, light scratch") == (None, 1)
    assert ds.story_claims("airbags went off, car totalled") == (None, 3)
    assert ds.story_claims("my car was damaged") == (None, None)


def test_vague_or_side_story_is_not_applicable():
    assert not ds.run("My car was damaged in an accident.", []).applicable
    assert not ds.run("I got T-boned at a junction.", []).applicable     # side, no severity: not judged
    assert not ds.run(None, []).applicable


def test_legit_stories_are_not_flagged():
    for sev in (1.0, 1.5, 2.0, 2.5):                     # any realistic photo
        assert ds.judge(None, 2, [read(sev, 0.5)])[0] == []      # "hit at 30 km/h"
    assert ds.judge("rear", 2, [read(1.5, 0.6)])[0] == []        # front-ish but not confident


def test_clear_contradictions_are_flagged():
    probs, ev = ds.judge(None, 3, [read(1.0, 0.5)])               # "totalled" vs a light scratch
    assert probs and "severe crash" in probs[0] and ev["expected_severity"] == 1.0
    assert ds.judge("rear", 2, [read(2.0, 0.9)])[0]               # rear claimed, confident front damage
    assert len(ds.judge("rear", 3, [read(1.0, 0.9)])[0]) == 2     # both at once


def test_best_matching_photo_decides():
    # one close-up looks like a scratch, another shows the crash: the claim is consistent
    assert ds.judge(None, 3, [read(1.0, 0.5), read(2.8, 0.5)])[0] == []
