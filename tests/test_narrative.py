"""Template narrative + background LLM swap. No network: llm.complete is monkeypatched."""
import time

from claimshield.contracts import ClaimScore, Signal
from claimshield.narrative import llm, template


def claim():
    sigs = [Signal("clip_probe", 0.9, 0.8, "Visual-feature probe: looks AI-generated (0.90)."),
            Signal("exif", 0.2, 0.4, "Camera metadata intact (Apple iPhone 13)."),
            Signal("name_mismatch", 1.0, 0.7, "The name on the ID (Asha Verma) differs from "
                   "the name on a claim document (Rahul Nair).", tier="claim")]
    return ClaimScore(0.8, None, None, 0.81, "HIGH",
                      [("baseline", 0.5), ("clip_probe", 0.2), ("name_mismatch", 0.07),
                       ("exif", -0.02)], [], sigs)


def test_template_is_deterministic_and_scrubbed():
    a, pii = template.build(claim(), ["Asha Verma", "Rahul Nair"])
    assert a == template.build(claim(), ["Asha Verma", "Rahul Nair"])[0]
    assert a.startswith("Overall: HIGH (0.81)") and "Main concerns: (1) Visual-feature" in a
    assert "Asha" not in a and "Rahul" not in a and "[NAME_1]" in a
    assert "Asha Verma" in template.fill(a, pii)


def test_scrub_patterns():
    t, pii = template.scrub("UHID 12345678, call +91 98765 43210, mail a.b@x.com, total 51,330.00")
    assert "12345678" not in t and "98765" not in t and "a.b@x.com" not in t
    assert "51,330.00" in t and template.fill(t, pii).startswith("UHID 12345678")


def test_llm_swap_only_within_timeout(monkeypatch):
    text, _ = template.build(claim(), ["Asha Verma", "Rahul Nair"])
    sent = []

    def slow(system, user, **kw):
        sent.append(user)
        time.sleep(5)
        return user
    monkeypatch.setattr(llm.llm, "complete", slow)
    t0 = time.perf_counter()
    assert llm.result(llm.start(text)) is None           # template stays
    assert time.perf_counter() - t0 < 4.5
    assert "Asha" not in sent[0] and "[NAME_1]" in sent[0]  # no PII in the payload


def test_llm_output_that_changes_a_number_is_rejected(monkeypatch):
    text, _ = template.build(claim(), ["Asha Verma", "Rahul Nair"])
    monkeypatch.setattr(llm.llm, "complete", lambda s, u, **kw: u.replace("0.81", "0.95"))
    assert llm.result(llm.start(text)) is None
    monkeypatch.setattr(llm.llm, "complete", lambda s, u, **kw: "Reworded. " + u)
    assert llm.result(llm.start(text)).startswith("Reworded.")
