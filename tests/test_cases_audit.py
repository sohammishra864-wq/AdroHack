"""Inbox case loading, band chips, and the hashes-only audit trail."""
from claimshield import audit, cases
from claimshield.contracts import ClaimScore


def test_case_roles_by_filename(tmp_path):
    for n in ("front.jpg", "idle_car.jpg", "id.png", "selfie.jpg", "invoice.pdf", "scan_bill.jpg",
              "case.json"):
        (tmp_path / n).write_bytes(b"x" if n != "case.json" else b'{"title": "Case B"}')
    c = cases.load(tmp_path)
    assert c.title == "Case B"
    assert [p.split("\\")[-1].split("/")[-1] for p in c.photos] == ["front.jpg", "idle_car.jpg"]
    assert c.id_path.endswith("id.png") and c.selfie.endswith("selfie.jpg")
    assert len(c.docs) == 2 and len(cases.hashes(c)) == 6


def test_band_chips_persist(tmp_path, monkeypatch):
    monkeypatch.setattr(cases, "BANDS", tmp_path / "b.json")
    cases.save_band("a", "HIGH")
    cases.save_band("b", "LOW")
    assert cases.last_bands() == {"a": "HIGH", "b": "LOW"}


def test_audit_row_per_action_hashes_only(tmp_path):
    db = tmp_path / "a.sqlite"
    claim = ClaimScore(0.8, None, None, 0.8, "HIGH", [("baseline", 0.5)], [], [])
    audit.record("case-b", ["ab" * 32], claim, "asha", "escalate", "check invoice", path=db)
    audit.record("case-b", ["ab" * 32], claim, "asha", "reject", path=db)
    h = audit.history("case-b", path=db)
    assert [r["action"] for r in h] == ["escalate", "reject"] and h[0]["band"] == "HIGH"
    try:
        audit.record("case-b", [], claim, "asha", "delete", path=db)
        raise AssertionError("bad action accepted")
    except ValueError:
        pass
